#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
import os.path
import os
import traceback
import flask
import calendar
import logging
from datetime import datetime
from collections import defaultdict
import requests

from gitlab import GitlabConnector
from ocp import OCPConnector
from utils import float2dec, get_fixed_incomes, get_fixed_budget, _parse_calculate_data
logging.basicConfig(level=logging.DEBUG)

# Create the application.
app = flask.Flask(__name__)

# TODO: to get from the getfaircoin API
FAIR2EUR_PRICE = 1.2


areas = [
    {'id': 'communication', 'name': 'Media/Communication', 'gitlab': [12], 'ocp': [437]},
    {'id': 'welcome', 'name': 'Welcome/Support/Human Cares', 'gitlab': [15], 'ocp': [455]},
    {'id': 'commonmanagement', 'name': 'Common Management', 'gitlab': [41], 'ocp': [474]},
    {'id': 'circulareconomy', 'name': 'Circular Economy', 'gitlab': [38], 'ocp': [459]},
    {'id': 'techarea', 'name': 'Tech Area', 'gitlab': [28], 'ocp': [475]},
    {'id': 'fairmarket', 'name': 'FairMarket', 'gitlab': [16], 'ocp': [512]},
    {'id': 'ocpdev', 'name': 'OCP Development', 'gitlab': [None], 'ocp': [547, 18]},
    {'id': 'faircoopwebsite', 'name': 'Website/Forum/Wiki/Blog', 'gitlab': [21], 'ocp': [549]},
    {'id': 'kispagi', 'name': 'Kispagi tool for OCW', 'gitlab': [35], 'ocp': [None]},
    {'id': 'invoices', 'name': 'invoices.freedomcoop.eu', 'gitlab': [34], 'ocp': [None]},
    {'id': 'usefaircoin', 'name': 'UseFaircoin', 'gitlab': [13], 'ocp': [None]},
    {'id': 'coopfunding', 'name': 'CoopFunding', 'gitlab': [80], 'ocp': [None]},
    {'id': 'extension', 'name': 'FC Extension', 'gitlab': [None], 'ocp': [713]}
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


@app.route('/calculate/', methods=['POST'])
def calculate():

    special_wallets = {'Sebastian': 'fcyrdjynkQzEBquGX7TmTvXodm2TQeAKDg',
                       'thokon00': 'fK5F4k5KxyUnYKCsUVPUaDs7pAgfWoBxHH',
                       'sofocles_dans': 'fGFmLSn8WkcXvwxkVa9wKGkJ51NV9wCjo8',
                       'cegroj': 'fYGHKViDbvsuHqUPSGDyU2vJtGYQmwVHyn'}
    data = flask.request.get_json()
    alerts = []
    settings, areas, users = _parse_calculate_data(data)
    total_budget = settings['budget-euros'] + settings['budget-faircoins'] * FAIR2EUR_PRICE
    logging.debug('Total budget in EUR {0}'.format(total_budget))
    results = {}
    total_fixed_incomes = 0
    total_payable_hours = 0
    total_eur_to_pay = 0
    users_to_be_paid = {}
    calculation_successful = True
    price_hour = 10

    for area_name, area in areas.items():
        alerts = []
        logging.debug('Calculating for {0}'.format(area_name))

        if 'users' not in area:
            area['users'] = {}
            alerts.append({'type': 'danger', 'msg': 'No contributors in the following area.'})
        for username, u in area['users'].items():
            # Calculating the sum of fix income for each user and the payable hours left
            if u['fix-income'] > 0:
                total_fixed_incomes += u['fix-income']
            else:
                u['fix-hours'] = 0

            u['payable_hours'] = float2dec(u['time'] / 3600) - u['fix-hours'] - u['volunteer-hours']
            if u['payable_hours'] < 0:
                u['payable_hours'] = 0

            users[username]['payable_hours'] += u['payable_hours']
            users[username]['tasks_time'] += u['payable_hours'] * 3600

            extra_time = u['time'] - u['fix-hours'] * 3600
            if extra_time >= 0 and (u['voluntary-time'] or u['volunteer-hours']):
                users[username]['voluntary_time'] += u['voluntary-time'] + u['volunteer-hours'] * 3600

            users[username]['fix-income'] += u['fix-income']
            users[username]['fixed_time'] += u['fix-hours'] * 3600
            total_payable_hours += u['payable_hours']

    # in case a fixed income user hasn't logged any hour yet
    # fixed_income_users = get_fixed_incomes(month=settings['month'])
    # for u in fixed_income_users:
    #     if u['username'] not in users:
    #         users[username]['payable_hours'] = 0
    #         users[username]['tasks_time'] = u['time'] + u['volunteer-hours'] * 3600
    #         users[username]['fix-income'] = u['fix-income']

    if total_budget < total_fixed_incomes:
        alert = 'Total budget is not enough for the fixed incomes: {0}€ < {1}€'.format(
            total_budget, total_fixed_incomes)
        alerts.append({'type': 'danger', 'msg': alert})
        calculation_successful = False
    else:
        left_budget = total_budget - total_fixed_incomes
        max_hour_alert = min_hour_alert = None
        if total_payable_hours > 0:
            max_salary_users = {}
            repeat = True
            while repeat:
                price_hour = float2dec(left_budget / float(total_payable_hours))
                if price_hour > settings['max-hour']:
                    alert = 'Price/hour was reduced to the general MAX_HOUR={1}€ \
                             because the calculated hour value is bigger: {0}€ > {1}€'.format(
                        float2dec(price_hour), settings['max-hour'])
                    max_hour_alert = {'type': 'warning', 'msg': alert}
                    price_hour = settings['max-hour']
                if price_hour < settings['min-hour']:
                    alert = 'Calculated price/hour is inferior to the general min-hour: {0}€ < {1}€'.format(
                        float2dec(price_hour), settings['min-hour'])
                    min_hour_alert = {'type': 'danger', 'msg': alert}

                repeat = False
                for username, u in users.items():
                    user_tasks_eur = u['payable_hours'] * price_hour
                    final_payment = float2dec(user_tasks_eur + u['fix-income'])
                    u['freelance_eur'] = float2dec(user_tasks_eur)
                    payment_detail = 'Fixed: {0}€, Tasks: {1}€'.format(u['fix-income'], u['freelance_eur'])
                    if final_payment > settings['max-month']:
                        alert = 'User {0} has reached maximum of monthly payment agreed: {1}€ > {2}€'.format(
                            username, int(final_payment), settings['max-month'])
                        alerts.append({'type': 'warning', 'msg': alert})
                        u['final_payment'] = settings['max-month']
                        u['payment_detail'] = '<font color="red">{0}€</font><font color="blue">({1} ƒ)</font> \
                                               <font color="red">MAX!</font> < {2}'.format(
                            settings['max-month'],
                            float2dec(settings['max-month'] / FAIR2EUR_PRICE),
                            payment_detail)
                        max_salary_users[username] = u
                        users.pop(username)
                        left_budget -= user_tasks_eur
                        total_payable_hours -= u['payable_hours']
                        repeat = True
                        break
                    else:
                        u['final_payment'] = final_payment
                        u['payment_detail'] = '<font color="red">{0}€</font>\
                                               <font color="blue">({1} ƒ)</font> = {2}'.format(
                            final_payment,
                            float2dec(final_payment / FAIR2EUR_PRICE),
                            payment_detail)

            # All users final payment calculated
            if max_hour_alert:
                alerts.append(max_hour_alert)
            if min_hour_alert:
                alerts.append(min_hour_alert)
            users.update(max_salary_users)
            total_eur_to_pay = 0

            for username, u in users.items():
                total_eur_to_pay += u['final_payment']
                if u['final_payment'] > 0:
                    users_to_be_paid[username] = u

            user_total = defaultdict(int)

            for username, u in users_to_be_paid.items():
                # print('user', username)
                logging.debug('user: {0} total_eur_to_pay {1} final_payment {2}'.format(
                    username, total_eur_to_pay, u['final_payment']))
                try:
                    percentage = float2dec(100 * (u['final_payment'] / total_eur_to_pay))
                except Exception:
                    logging.debug(traceback.format_exc())
                    percentage = 0
                u['percentage'] = percentage
                logging.debug('Percentage from total: {0}'.format(percentage))

                if 'all_users' in globals():
                    u.update(all_users[username])
                    if username in special_wallets:
                        u['ocp_faircoin_address'] = special_wallets[username]

                user_total['fix-income'] += u['fix-income']
                user_total['freelance_eur'] += u['freelance_eur']
                user_total['final_payment'] += u['final_payment']
                user_total['fixed_time'] += u['fixed_time']
                user_total['voluntary_time'] += u['voluntary_time']
                user_total['tasks_time'] += u['tasks_time']

            # Adding the total row
            user_total['percentage'] = float2dec(100 * (user_total['final_payment'] / total_eur_to_pay))
            user_total['payment_detail'] = '<font color="red">{0}€</font><font color="blue">({1} ƒ)</font>\
                                            = Fixed: {2}€, Tasks: {3}€'.format(
                                           user_total['final_payment'],
                                           float2dec(user_total['final_payment'] / FAIR2EUR_PRICE),
                                           user_total['fix-income'],
                                           user_total['freelance_eur'])
            users_to_be_paid['TOTAL'] = user_total

    # Calculating money paid and left
    results['total_euros_left'] = total_budget - total_eur_to_pay
    f = settings['budget-faircoins'] * FAIR2EUR_PRICE - total_eur_to_pay
    if f > 0:
        results['faircoins_left'] = float2dec(f / FAIR2EUR_PRICE)
        results['euros_left'] = settings['budget-euros']
    else:
        results['faircoins_left'] = 0
        results['euros_left'] = float2dec(settings['budget-euros'] + f)

    if calculation_successful:
        money_left_msg = ""
        if results['total_euros_left'] > 0.1:
            if results['euros_left'] >= 0.1:
                money_left_msg = '{0}ƒ + {1}€'.format(float2dec(results['faircoins_left']),
                                                               float2dec(results['euros_left']))
            else:
                money_left_msg = '{0}ƒ'.format(float2dec(results['faircoins_left']))

        msg = """Calculation successful.<br/>
                 Final Price/hour: {0}€<br/>
                 Total budget: {1}€ / {2}ƒ<br/>
                 Total to pay: {3}€ / {4}ƒ<br/>
                 Total Left: {5}€ / {6}""".format(float2dec(price_hour),
                                                  float2dec(total_budget), float2dec(total_budget / FAIR2EUR_PRICE),
                                                  float2dec(total_eur_to_pay),
                                                  float2dec(total_eur_to_pay / FAIR2EUR_PRICE),
                                                  float2dec(results['total_euros_left']), money_left_msg)
        alerts.append({'type': 'success', 'msg': msg})
    results['alerts'] = alerts
    results['users'] = users_to_be_paid

    for _, details in users_to_be_paid.items():
        if details.get('email', None):
            print(details['email'])

    return flask.jsonify(results)


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
    gitlab = GitlabConnector()
    ocp = OCPConnector()
    global all_users

    all_users = {}
    ocp_error_connection = False
    gitlab.get_server_users()
    ocp.get_server_users()

    for area in areas:
        contributions_gitlab = []
        contributions_ocp = []
        logging.debug('Checking area: {0}'.format(area['name']))

        project_id = area['gitlab'][0]
        if project_id:
            issues = gitlab.get_issues(project_id=project_id)
            contributions_gitlab, gitlab_users = gitlab.parse_issues(issues, project_id, date_min, date_max)
            for username, user in gitlab_users.items():
                if username in all_users:
                    all_users[username].update(user)
                else:
                    all_users[username] = user

        for project_id in area['ocp']:
            if project_id:
                ocp_users = {}
                logging.debug('OCP project_id: {0}'.format(project_id))
                contributions_project_ocp = []
                if not ocp_error_connection:
                    try:
                        issues = ocp.get_data(project_id=project_id)
                        contributions_project_ocp, ocp_users = ocp.parse_issues(issues, project_id,
                                                                                date_min, date_max, gitlab)
                    except requests.exceptions.ReadTimeout:
                        ocp_error_connection = True


                for username, user in ocp_users.items():
                    if username in all_users:
                        all_users[username].update(user)
                    else:
                        all_users[username] = user
                contributions_ocp += contributions_project_ocp

        contributions = contributions_gitlab + contributions_ocp

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
