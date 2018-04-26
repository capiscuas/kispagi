#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
import os.path
import os

import flask
import calendar
import logging
import requests
from datetime import datetime
from itertools import chain
from collections import defaultdict

from gitlab import GitlabConnector
from redmine import RedmineConnector
from ocp import OCPConnector
from utils import get_fixed_incomes, get_fixed_budget, FAIR2EUR_PRICE
import distribution
import ocw_hours

logging.basicConfig(level=logging.DEBUG)

# Create the application.
app = flask.Flask(__name__)

# TODO: to get from the getfaircoin API


areas = [
    {'id': 'communication', 'name': 'Media/Communication', 'gitlab': 12, 'ocp': [437], 'redmine': ['media-communication']},
    {'id': 'welcome', 'name': 'Welcome/Support/Human Cares', 'gitlab': 15, 'ocp': [455],
                                                             'redmine': ['welcome-support-education-human-cares']},
    {'id': 'commonmanagement', 'name': 'Common Management', 'gitlab': 41, 'ocp': [474], 'redmine': ['common-management']},
    {'id': 'circulareconomy', 'name': 'Circular Economy', 'gitlab': 38, 'ocp': [459], 'redmine': ['circular-economy']},
    {'id': 'techarea', 'name': 'Tech Area', 'gitlab': 28, 'ocp': [475], 'redmine': ['tech-area']},
    {'id': 'fairmarket', 'name': 'FairMarket', 'gitlab': 16, 'ocp': [512], 'redmine': ['fairmarket']},
    {'id': 'ocpdev', 'name': 'OCP Development',  'ocp': [547, 18]},
    {'id': 'faircoopwebsite', 'name': 'Website/Forum/Wiki/Blog', 'gitlab': 21, 'ocp': [549], 'redmine': ['fair-coop-website']},
    {'id': 'kispagi', 'name': 'Kispagi', 'gitlab': 35, 'redmine': ['kispagi']},
    {'id': 'invoices', 'name': 'invoices.freedomcoop.eu', 'gitlab': 34, 'redmine': ['freedomcoop-invoices']},
    {'id': 'usefaircoin', 'name': 'UseFaircoin', 'gitlab': 13, 'redmine': ['usefaircoin']},
    {'id': 'coopfunding', 'name': 'CoopFunding', 'gitlab': 80, 'redmine': ['coopfunding']},
    {'id': 'extension', 'name': 'Extension', 'ocp': [713], 'redmine': ['extension']}
]

try:
    from env.settings import areas_test
    areas = areas_test
except Exception:
    pass

try:
    from env.settings import home_directory
    os.chdir(home_directory)
except Exception:
    pass


app.add_url_rule('/calculate/', 'calculate', distribution.calculate, methods=['POST'])


@app.route('/')
def index():
    alerts = []
    month_param = flask.request.args.get('month', default='04-2018', type=str)
    fname = '{0}.html'.format(month_param)
    if os.path.isfile(os.path.join('templates', fname)):
        logging.debug('Found Results template {0}'.format(fname))
        return flask.render_template(fname)
    logging.debug('Month requested: {0}'.format(month_param))
    try:
        splitted_month = month_param.split('-')
        month = int(splitted_month[0])
        year = int(splitted_month[1])
        date_min = datetime(year, month, 1, 0, 0)
        weekday, max_day = calendar.monthrange(year, month)
        date_max = datetime(year, month, max_day, 0, 0)
    except Exception:
        year = 2018
        month = 2
        weekday, max_day = calendar.monthrange(year, month)
        date_min = datetime(year, month, 1, 0, 0)
        date_max = datetime(year, month, max_day, 0, 0)
    settings = {'FAIR2EUR_PRICE': FAIR2EUR_PRICE,
                'month_name': date_min.strftime("%B '%y")}
    settings['fixed_income_users'] = get_fixed_incomes(month=month_param)
    settings['fixed_budget'] = get_fixed_budget(month=month_param)
    app.gitlab = GitlabConnector()
    app.ocp = OCPConnector(app)
    redmine = RedmineConnector()
    global all_users

    all_users = defaultdict(dict)
    ocp_error_connection = False
    redmine.get_server_users()
    app.gitlab.get_server_users()
    app.ocp.get_server_users()

    for area in areas:

        logging.debug('Checking area: {0}'.format(area['name']))
        contributions_redmine = []
        for project_id in area.get('redmine', []):
            contributions, redmine_users = redmine.get_issues(project_id, date_min, date_max)
            for username, user in redmine_users.items():
                all_users[username].update(user)

        remunerated_work, voluntary_work = ocw_hours.filter_by_remuneration(contributions)
        remunerated_work = ocw_hours.validate_remunerations(remunerated_work)

        contributions_redmine = []
        for x in chain(remunerated_work.values(), voluntary_work.values()):
            for w in x.values():
                contributions_redmine.append(w)

        contributions_gitlab = []
        project_id = area.get('gitlab', None)
        if project_id:
            issues = app.gitlab.get_issues(project_id=project_id)
            contributions_gitlab, gitlab_users = app.gitlab.parse_issues(issues, project_id, date_min, date_max)
            for username, user in gitlab_users.items():
                all_users[username].update(user)

        sum_contributions_ocp = []
        for project_id in area.get('ocp', []):
            if project_id:
                ocp_users = {}
                logging.debug('OCP project_id: {0}'.format(project_id))
                contributions_project_ocp = []
                if not ocp_error_connection:
                    try:
                        issues = app.ocp.get_data(project_id=project_id)
                        contributions_project_ocp, ocp_users = app.ocp.parse_issues(issues, project_id, date_min, date_max)
                    except requests.exceptions.ReadTimeout:
                        ocp_error_connection = True  # If at least 1 OCP project fails to answer, we stop requesting the others

                for username, user in ocp_users.items():
                    all_users[username].update(user)
                sum_contributions_ocp += contributions_project_ocp

        contributions_ocp = []
        remunerated_work, voluntary_work = ocw_hours.filter_by_remuneration(sum_contributions_ocp)
        remunerated_work = ocw_hours.validate_remunerations(remunerated_work)

        for x in chain(remunerated_work.values(), voluntary_work.values()):
            for w in x.values():
                contributions_ocp.append(w)

        # Merging the 3 time loggers
        contributions = contributions_gitlab + contributions_ocp + contributions_redmine

        not_validated_tasks = {}
        validated_tasks = {}
        voluntary_tasks = {}
        users_list = {}
        for c in contributions:
            user = c['username']
            if user not in validated_tasks:
                not_validated_tasks[user] = []
                validated_tasks[user] = []
                voluntary_tasks[user] = []
                users_list[user] = {'total_time_spent': 0, 'total_time_voluntary': 0}
            if not c['is_voluntary']:
                if c['validated']:
                    users_list[user]['total_time_spent'] += c['total_time_spent']
                    validated_tasks[user].append(c)
                else:
                    not_validated_tasks[user].append(c)
            else:
                users_list[user]['total_time_voluntary'] += c['total_time_spent']
                voluntary_tasks[user].append(c)

        for user in users_list.keys():
            users_list[user]['validated_tasks'] = validated_tasks[user]
            users_list[user]['tasks'] = not_validated_tasks[user]
            users_list[user]['voluntary_tasks'] = voluntary_tasks[user]

        area['tasks'] = contributions
        area['users'] = users_list

    if ocp_error_connection:
        alerts.append({'type': 'danger', 'msg': 'OCP connection failed when accessing some projects. Contact OCP admins.'})

    return flask.render_template('index.html', settings=settings, areas=areas, alerts=alerts)


if __name__ == '__main__':
    app.debug = True
    app.run()
