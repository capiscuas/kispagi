#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
import os.path
import os
import pickle
import flask
import calendar
import logging
import requests
import traceback
import notifications
from datetime import datetime
from itertools import chain
from collections import defaultdict

from gitlab import GitlabConnector
from redmine import RedmineConnector
from ocp import OCPConnector
from utils import get_fixed_incomes, get_fixed_budget, FAIR2EUR_PRICE
import distribution
import ocw_hours
import faircoop

logging.basicConfig(level=logging.DEBUG)

# Create the application.
app = flask.Flask(__name__)

# TODO: to get from the getfaircoin API

app.dir_path = os.path.dirname(os.path.realpath(__file__))
try:
    # from env.settings import home_directory
    os.chdir(app.dir_path)
except Exception:
    pass


app.add_url_rule('/calculate/', 'calculate', distribution.calculate, methods=['POST'])
app.add_url_rule('/recent.atom', 'generate_feed', notifications.generate_feed)

app.all_users = defaultdict(dict)


@app.route('/')
def index():
    areas = faircoop.areas
    try:
        from env.settings import areas_test
        areas = areas_test
    except Exception:
        pass

    alerts = []
    default_month = '04-2018'
    next_month = '05-2018'
    month_param = flask.request.args.get('month', default=default_month, type=str)
    if month_param == 'next':
        month_param = next_month

    fname = '{0}.html'.format(month_param)
    if os.path.isfile(os.path.join(app.dir_path, 'templates', fname)):
        logging.debug('Found Results template {0}'.format(fname))
        return flask.render_template(fname)

    logging.debug('Month requested: {0}'.format(month_param))
    try:
        splitted_month = month_param.split('-')
        month = int(splitted_month[0])
        year = int(splitted_month[1])
    except:
        month_param = default_month
        splitted_month = month_param.split('-')
        month = int(splitted_month[0])
        year = int(splitted_month[1])

    date_min = datetime(year, month, 1, 0, 0)
    weekday, max_day = calendar.monthrange(year, month)
    date_max = datetime(year, month, max_day, 0, 0)

    settings = {'FAIR2EUR_PRICE': FAIR2EUR_PRICE,
                'month_name': date_min.strftime("%B '%y")}
    settings['fixed_income_users'] = get_fixed_incomes(month=month_param)
    settings['fixed_budget'] = get_fixed_budget(month=month_param)
    ocp_error_connection = False
    app.gitlab = GitlabConnector()
    app.ocp = OCPConnector(app)
    redmine = RedmineConnector()

    cache_time_file = os.path.join('/tmp/', 'cache_time_' + month_param + '.p')
    cache_areas_file = os.path.join('/tmp/', 'cache_areas_' + month_param + '.p')
    cache_all_time_events_file = os.path.join('/tmp/', 'cache_all_time_events_' + month_param + '.p')
    cache_kispagi_users = os.path.join('/tmp/', 'cache_kispagi_users.p')
    areas_cache = None
    all_time_events_cache = None

    cache_default_time_refresh = 10
    now = datetime.now()

    force_cache_refresh = flask.request.args.get('cache', default=False, type=bool)
    try:
        cache_latest_time = pickle.load(open(cache_time_file, "rb"))
        areas_cache = pickle.load(open(cache_areas_file, "rb"))
        all_time_events_cache = pickle.load(open(cache_all_time_events_file, "rb"))
        logging.debug('Recovering contributions from cache')
    except Exception:
        logging.debug(traceback.format_exc())
        cache_latest_time = now
        force_cache_refresh = True

    if force_cache_refresh:
        logging.debug('reloading_contributions from API')
        redmine.get_server_users()
        app.gitlab.get_server_users()
        app.ocp.get_server_users()
        all_time_events = []

        for area in areas:
            area_name = area['name']
            logging.debug('Checking area: {0}'.format(area_name))
            sum_contributions_redmine = []
            for project_id in area.get('redmine', []):
                contributions, redmine_users = redmine.get_issues(area_name, project_id, date_min, date_max)
                for username, user in redmine_users.items():
                    app.all_users[username].update(user)
                sum_contributions_redmine += contributions

            all_time_events += sum_contributions_redmine
            remunerated_work, voluntary_work = ocw_hours.filter_by_remuneration(sum_contributions_redmine)
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
                    app.all_users[username].update(user)

            sum_contributions_ocp = []
            for project_id in area.get('ocp', []):
                if project_id:
                    ocp_users = {}
                    logging.debug('OCP project_id: {0}'.format(project_id))
                    contributions_project_ocp = []
                    if not ocp_error_connection:
                        try:
                            issues = app.ocp.get_data(project_id=project_id)
                            contributions_project_ocp, ocp_users = app.ocp.parse_issues(issues, area_name,
                                                                                        project_id, date_min, date_max)
                        except requests.exceptions.ReadTimeout:
                            # If at least 1 OCP project fails to answer, we stop requesting the others
                            ocp_error_connection = True

                    for username, user in ocp_users.items():
                        app.all_users[username].update(user)
                    sum_contributions_ocp += contributions_project_ocp

            contributions_ocp = []
            all_time_events += sum_contributions_ocp
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
        alerts.append({'type': 'danger', 'msg': 'OCP API time out. Recovering last cache data. Contact OCP admins.'})
        logging.debug('OCP API failed, recovering cache')
        if areas_cache:
            areas = areas_cache

    elif force_cache_refresh:
        cache_latest_time = now
        pickle.dump(areas, open(cache_areas_file, "wb"))
        pickle.dump(now, open(cache_time_file, "wb"))

        pickle.dump(all_time_events, open(cache_all_time_events_file, "wb"))

        pickle.dump(app.all_users, open(cache_kispagi_users, "wb"))
        notifications.check_time_event_changes(new=all_time_events, old=all_time_events_cache)
    elif areas_cache:
        areas = areas_cache

    settings['cache_latest_time'] = cache_latest_time
    settings['cache_default_time_refresh'] = cache_default_time_refresh
    alerts.append({'type': 'warning', 'msg': 'Next OCW assembly: 14th of May at 19h00(CEST). Make sure to validate your April work before that day.'})

    return flask.render_template('index.html', settings=settings, areas=areas, alerts=alerts)


if __name__ == '__main__':
    app.debug = True
    app.run()
