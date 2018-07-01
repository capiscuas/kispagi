#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division

FAIR2EUR_PRICE = 1.2


def transform_int(number):
    string = str(number).split('.')
    if len(string) > 1:
        if string[1].startswith('00') or string[1] == '0':
            return int(number)

    return number


def float2dec(number):
    number = transform_int(number)
    if not type(number) == int:
        rounded = float('{0:.2f}'.format(number))
        if rounded > number:
            rounded = float('{0:.2f}'.format(number - 0.01))

        return rounded
    else:
        return number


def _parse_calculate_data(data):
    # TODO: refactor DRY
    settings = {}
    users = {}
    data_settings = data[0]
    data_areas = data[1]
    areas = {}

    def _add_user_value(areas, area, username, key, value):
        if area not in areas:
            areas[area] = {'users': {}}
        elif 'users' not in areas[area]:
            areas[area]['users'] = {}

        _add_value(areas[area]['users'], username, key, value)

        users[username] = {'payable_hours': 0,
                           'fix-income': 0,
                           'tasks_time': 0,
                           'fixed_time': 0,
                           'voluntary_time': 0}

    def _add_value(d, key, subkey, value):
        if key in d:
            d[key][subkey] = value
        else:
            d[key] = {subkey: value}

    for d in data_settings:
        k = d['name']
        v = d['value']
        if k == 'max-hour':
            settings['max-hour'] = float2dec(float(v))
        elif k == 'min-hour':
            settings['min-hour'] = float2dec(float(v))
        elif k == 'max-month':
            settings['max-month'] = float2dec(float(v))
        elif k == 'budget-faircoins':
            settings['budget-faircoins'] = float2dec(float(v))
        elif k == 'budget-euros':
            settings['budget-euros'] = float2dec(float(v))

    for d in data_areas:
        k = d['name']
        v = d['value']

        if k.startswith('volunteer-hours-'):
            area_user = k[len('volunteer-hours-'):].split('--')
            area = area_user[0]
            username = area_user[1]
            _add_user_value(areas, area, username, 'volunteer-hours', float2dec(float(v)))
        elif k.startswith('fix-hours-'):
            area_user = k[len('fix-hours-'):].split('--')
            area = area_user[0]
            username = area_user[1]
            if not v:
                v = 0
            _add_user_value(areas, area, username, 'fix-hours', float2dec(float(v)))
        elif k.startswith('fix-income-'):
            area_user = k[len('fix-income-'):].split('--')
            area = area_user[0]
            username = area_user[1]
            if not v:
                v = 0
            _add_user_value(areas, area, username, 'fix-income', float2dec(float(v)))
        elif k.startswith('time-'):
            area_user = k[len('time-'):].split('--')
            area = area_user[0]
            username = area_user[1]
            _add_user_value(areas, area, username, 'time', int(float(v)))
        elif k.startswith('voluntary-time-'):
            area_user = k[len('voluntary-time-'):].split('--')
            area = area_user[0]
            username = area_user[1]
            _add_user_value(areas, area, username, 'voluntary-time', int(float(v)))

    return settings, areas, users


users_db = [{'ocp': 'berzas', 'gitlab': 'berzas_berzas'},
            {'ocp': 'IvanEsperanto', 'gitlab': 'kapis'},
            {'redmine': 'Onix228', 'gitlab': 'coly_boubacar_d'}]

special_wallets = {}


def get_unique_username(key=None, value=None):
    username = {}
    for u in users_db:
        if key in u and u[key] == value:
            username = u
            break

    if key != 'redmine' and 'redmine' in username:
        return 'redmine', username['redmine']
    if key != 'ocp' and 'ocp' in username:
        return 'ocp', username['ocp']
    return None, None


fixed_month_values = {
    '09-2017': {'budget-faircoins': 6444.4444,
                'users': [
                    {'username': 'maro', 'fix_hours': 80, 'fix_income': 600, 'area': 'commonmanagement'},
                    {'username': 'javier_mckleyn', 'fix_hours': 40, 'fix_income': 250, 'area': 'commonmanagement'},
                    {'username': 'edgar_nomada', 'fix_hours': 168, 'fix_income': 1050, 'area': 'commonmanagement'},
                    {'username': 'santi', 'fix_hours': 80, 'fix_income': 600, 'area': 'fairmarket'},
                    {'username': 'berzas', 'fix_hours': 80, 'fix_income': 500, 'area': 'techarea'},
                    {'username': 'cegroj', 'fix_hours': 80, 'fix_income': 500, 'area': 'techarea'}]},

    '10-2017': {'budget-faircoins': 11111.12,
                'users': [
                    {'username': 'maro', 'fix_hours': 80, 'fix_income': 600, 'area': 'commonmanagement'},
                    {'username': 'javier_mckleyn', 'fix_hours': 40, 'fix_income': 250, 'area': 'commonmanagement'},
                    {'username': 'edgar_nomada', 'fix_hours': 56, 'fix_income': 350, 'area': 'commonmanagement'},
                    {'username': 'santi', 'fix_hours': 80, 'fix_income': 600, 'area': 'fairmarket'},
                    {'username': 'berzas', 'fix_hours': 80, 'fix_income': 500, 'area': 'techarea'},
                    {'username': 'cegroj', 'fix_hours': 80, 'fix_income': 500, 'area': 'techarea'},
                    {'username': 'michalis_kassapakis', 'fix_hours': 80, 'fix_income': 500, 'area': 'circulareconomy'},
                    {'username': 'juanse_h', 'fix_hours': 80, 'fix_income': 500, 'area': 'circulareconomy'}]},

    '11-2017': {'budget-faircoins': 10000,
                'users': [
                    {'username': 'maro', 'fix_hours': 80, 'fix_income': 600, 'area': 'commonmanagement'},
                    {'username': 'javier_mckleyn', 'fix_hours': 100, 'fix_income': 600, 'area': 'commonmanagement'},
                    {'username': 'santi', 'fix_hours': 80, 'fix_income': 600, 'area': 'fairmarket'},
                    {'username': 'berzas', 'fix_hours': 80, 'fix_income': 500, 'area': 'techarea'},
                    {'username': 'cegroj', 'fix_hours': 80, 'fix_income': 500, 'area': 'techarea'},
                    {'username': 'onix228', 'fix_hours': 80, 'fix_income': 500, 'area': 'techarea'},
                    {'username': 'alex_berbel', 'fix_hours': 120, 'fix_income': 750, 'area': 'techarea'},
                    {'username': 'michalis_kassapakis', 'fix_hours': 80, 'fix_income': 500, 'area': 'circulareconomy'},
                    {'username': 'pilikum_l_kerill', 'fix_hours': 50, 'fix_income': 300, 'area': 'communication'}]},

     #6,25eur per hour for fixed income, with extensions 6eur exceptionality
    '12-2017': {'budget-faircoins': 10000,
                'users': [
                    {'username': 'maro', 'fix_hours': 96, 'fix_income': 600, 'area': 'commonmanagement'},
                    {'username': 'javier_mckleyn', 'fix_hours': 96, 'fix_income': 600, 'area': 'commonmanagement'},
                    {'username': 'santi', 'fix_hours': 96, 'fix_income': 600, 'area': 'fairmarket'},
                    {'username': 'berzas', 'fix_hours': 80, 'fix_income': 500, 'area': 'techarea'},
                    {'username': 'cegroj', 'fix_hours': 80, 'fix_income': 500, 'area': 'techarea'},
                    {'username': 'al-demon', 'fix_hours': 120, 'fix_income': 750, 'area': 'techarea'},
                    {'username': 'michalis_kassapakis', 'fix_hours': 80, 'fix_income': 500, 'area': 'circulareconomy'},
                    {'username': 'pilikum_l_kerill', 'fix_hours': 48, 'fix_income': 300, 'area': 'communication'},
                    {'username': 'averiada', 'fix_hours': 43, 'fix_income': 258, 'area': 'extension'},
                    {'username': 'edgar_nomada', 'fix_hours': 43, 'fix_income': 258, 'area': 'extension'},
                    {'username': 'nikola_buric', 'fix_hours': 5, 'fix_income': 30, 'area': 'extension'}]},

    '01-2018': {'budget-faircoins': 8333.33,
                'users': [
                    {'username': 'maro', 'fix_hours': 80, 'fix_income': 500, 'area': 'commonmanagement'},
                    {'username': 'javier_mckleyn', 'fix_hours': 96, 'fix_income': 600, 'area': 'commonmanagement'},
                    {'username': 'santi', 'fix_hours': 96, 'fix_income': 600, 'area': 'fairmarket'},
                    {'username': 'berzas', 'fix_hours': 80, 'fix_income': 500, 'area': 'techarea'},
                    {'username': 'cegroj', 'fix_hours': 80, 'fix_income': 500, 'area': 'techarea'},
                    {'username': 'al_demon', 'fix_hours': 80, 'fix_income': 500, 'area': 'techarea'},
                    {'username': 'michalis_kassapakis', 'fix_hours': 80, 'fix_income': 500, 'area': 'circulareconomy'},
                    {'username': 'pilikum_l_kerill', 'fix_hours': 48, 'fix_income': 300, 'area': 'communication'}]},

    '02-2018': {'budget-faircoins': 8333.33,
                'users': [
                    {'username': 'maro', 'fix_hours': 80, 'fix_income': 500, 'area': 'commonmanagement'},
                    {'username': 'javier_mckleyn', 'fix_hours': 96, 'fix_income': 600, 'area': 'commonmanagement'},
                    {'username': 'santi', 'fix_hours': 96, 'fix_income': 600, 'area': 'fairmarket'},
                    {'username': 'berzas', 'fix_hours': 96, 'fix_income': 600, 'area': 'techarea'},
                    {'username': 'cegroj', 'fix_hours': 96, 'fix_income': 600, 'area': 'techarea'},
                    {'username': 'al_demon', 'fix_hours': 80, 'fix_income': 500, 'area': 'techarea'},
                    {'username': 'michalis_kassapakis', 'fix_hours': 80, 'fix_income': 500, 'area': 'circulareconomy'},
                    {'username': 'pilikum_l_kerill', 'fix_hours': 48, 'fix_income': 300, 'area': 'communication'}]},
    '03-2018': {'budget-faircoins': 8333.33,
                'users': [
                    {'username': 'maro', 'fix_hours': 80, 'fix_income': 500, 'area': 'commonmanagement'},
                    {'username': 'javierstb', 'fix_hours': 96, 'fix_income': 600, 'area': 'commonmanagement'},
                    {'username': 'santi', 'fix_hours': 96, 'fix_income': 600, 'area': 'fairmarket'},
                    {'username': 'berzas', 'fix_hours': 96, 'fix_income': 600, 'area': 'techarea'},
                    {'username': 'cegroj', 'fix_hours': 96, 'fix_income': 600, 'area': 'techarea'},
                    {'username': 'al_demon', 'fix_hours': 80, 'fix_income': 500, 'area': 'techarea'},
                    {'username': 'michalis_kassapakis', 'fix_hours': 80, 'fix_income': 500, 'area': 'circulareconomy'},
                    {'username': 'pilikum_l_kerill', 'fix_hours': 48, 'fix_income': 300, 'area': 'communication'}]},
    '04-2018': {'budget-faircoins': 8333.33,
                'users': [
                    {'username': 'maro', 'fix_hours': 80, 'fix_income': 500, 'area': 'commonmanagement'},
                    {'username': 'javierstb', 'fix_hours': 96, 'fix_income': 600, 'area': 'commonmanagement'},
                    {'username': 'santi', 'fix_hours': 96, 'fix_income': 600, 'area': 'fairmarket'},
                    {'username': 'berzas', 'fix_hours': 96, 'fix_income': 600, 'area': 'techarea'},
                    {'username': 'cegroj', 'fix_hours': 96, 'fix_income': 600, 'area': 'techarea'},
                    {'username': 'Al-Demon', 'fix_hours': 80, 'fix_income': 500, 'area': 'techarea'},
                    {'username': 'michalis_kassapakis', 'fix_hours': 80, 'fix_income': 500, 'area': 'circulareconomy'},
                    {'username': 'pilikum_l_kerill', 'fix_hours': 48, 'fix_income': 300, 'area': 'communication'}]},

    '05-2018': {'budget-faircoins': 8333.33,
                'users': [
                    {'username': 'maro', 'fix_hours': 80, 'fix_income': 500, 'area': 'commonmanagement'},
                    {'username': 'javier_mckleyn', 'fix_hours': 96, 'fix_income': 600, 'area': 'commonmanagement'},
                    {'username': 'berzas', 'fix_hours': 96, 'fix_income': 600, 'area': 'techarea'},
                    {'username': 'cegroj', 'fix_hours': 96, 'fix_income': 600, 'area': 'techarea'},
                    {'username': 'pilikum_l_kerill', 'fix_hours': 48, 'fix_income': 300, 'area': 'communication'}]},

    '06-2018': {'budget-faircoins': 8333.33,
                'users': [
                    {'username': 'maro', 'fix_hours': 80, 'fix_income': 500, 'area': 'commonmanagement'},
                    {'username': 'javier_mckleyn', 'fix_hours': 96, 'fix_income': 600, 'area': 'commonmanagement'},
                    {'username': 'berzas', 'fix_hours': 96, 'fix_income': 600, 'area': 'techarea'},
                    {'username': 'cegroj', 'fix_hours': 96, 'fix_income': 600, 'area': 'techarea'},
                    {'username': 'pilikum_l_kerill', 'fix_hours': 48, 'fix_income': 300, 'area': 'communication'}]}

}


def get_fixed_incomes(month=None):
    if month in fixed_month_values:
        return fixed_month_values[month]['users']
    else:
        return []


def get_fixed_budget(month=None):
    if month in fixed_month_values:
        return fixed_month_values[month]['budget-faircoins']
    else:
        return 0
