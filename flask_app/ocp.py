#!/usr/bin/env python
# -*- coding: utf-8 -*-

from collections import defaultdict
import requests


from dateutil.parser import parse as parse_date
from datetime import timedelta
from slugify import slugify
import json
import logging

from utils import _is_validated_comment
logging.basicConfig(level=logging.DEBUG)

try:
    from env.settings import ocp_token
except Exception:
    logging.error("ocp_token not defined in env/settings.py, you should created it")

try:
    from env.settings import ocp_host
except Exception:
    logging.error("ocp_host not defined in env/settings.py, you should created it")

CHECK_PROCESS_DATES = False


def _add_ocp_duration_to_date(date, duration):
    if 'day' not in duration:
        days = 0
    else:
        days = int(duration[:duration.find('day') - 1])

    return date + timedelta(days=days)


class OCPConnector(object):
    server_email2agent = {}
    server_agent2email = {}
    server_email2username = {}

    def get_ocp_faircoin_address(self, agent_id):
        pass
        # https://ocp.freedomcoop.eu/work/agent/56/

    def get_server_users(self):
        users2emails = {}
        with open('env/ocp.users.json') as data_file:
            data = json.load(data_file)

        for user in data:
            email = user['email']
            users2emails[user['api_url']] = email
            self.server_email2username[email] = user['username']

        with open('env/ocp.agents.json') as data_file:
            data = json.load(data_file)

        for agent in data:
            if agent['user'] in users2emails:
                email = users2emails[agent['user']]
                agent_id = int(agent['agent'].split("/")[-2])
                self.server_email2agent[email] = agent_id
                self.server_agent2email[agent_id] = email

    def get_data(self, project_id):
        issues_url = '{0}/v4/projects/{1}/issues'.format(ocp_host, project_id)
        query = """query($token: String) {
                      viewer(token: $token) { agent(id:""" + str(project_id) + """) { name
                          agentProcesses {
                            name id  plannedStart plannedDuration
                            unplannedEconomicEvents { id note }
                            committedInputs { note id fulfilledBy { fulfilledBy { id }}}
                            inputs {
                              id start
                              provider {id name faircoinAddress} action note requestDistribution
                              affectedQuantity{ numericValue unit {name}} note
                            }
                            processClassifiedAs {name} plannedDuration isFinished note
                          }
                        }
                      }}"""
        token = """{{"{0}": "{1}"}}""".format('token', ocp_token)
        headers = {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"}
        try:
            response = requests.get(issues_url,
                                    headers=headers,
                                    params={'query': query, 'variables': token}, timeout=30)

            return json.loads(response.text)
        except Exception:
            logging.debug('Error getting OCP request from API')

        return None

    def parse_issues(self, issues, project_id, date_min, date_max):
        contributions = []
        processes = issues["data"]["viewer"]["agent"]["agentProcesses"]

        ocp_users = {}
        for p in processes:
            web_url = 'https://ocp.freedomcoop.eu/work/process-logging/{0}/'.format(p['id'])
            process_work = {}
            voluntary_work = {}
            contributors = set()
            commitments = {}

            if CHECK_PROCESS_DATES:
                date_process_start = parse_date(p['plannedStart'])
                duration_str = p['plannedDuration']
                date_process_end = _add_ocp_duration_to_date(date_process_start, duration_str)
                if date_min > date_process_end or date_max < date_process_start:
                    continue
            # if p["isFinished"]:  disabled for the moment  bcs in OCW they are not finishing them.
            for c in p["committedInputs"]:
                c_id = c["id"]
                workevents = []
                commitments[c_id] = defaultdict(set)
                for f in c["fulfilledBy"]:
                    workevent_id = f["fulfilledBy"]["id"]
                    workevents.append(workevent_id)
                commitments[c_id]['events'] = workevents
                commitments[c_id]['title'] = c['note']

            workevents = []
            for u in p["unplannedEconomicEvents"]:
                workevents.append(u["id"])
                if u["note"] == 'NOKISPAGI':
                    break
            else:  # if not ignored by NOKISPAGI
                if len(workevents):
                    commitments["unplanned"] = defaultdict(set)
                    commitments["unplanned"]['events'] = workevents
                    commitments["unplanned"]['title'] = 'Unplanned work'

                inputs = {}
                for i in p["inputs"]:  # Extracting contributors and hours
                    inputs[i["id"]] = i

                for commitment_id, commitment in commitments.items():
                    for w_id in commitment['events']:
                        i = inputs[w_id]
                        # user_id = i['provider']['id']
                        username = slugify(i['provider']['name']).replace("-", "_")
                        user_id = i['provider']['id']
                        alias = None
                        email = None
                        if int(user_id) in self.server_agent2email:
                            email = self.server_agent2email[int(user_id)]
                            if email in self.server_email2username:
                                alias = self.server_email2username[email]
                        user_faircoinaddress = i['provider']['faircoinAddress']
                        if username not in ocp_users:
                            ocp_users[username] = {"ocp_username": username, "ocp_id": user_id,
                                                   "ocp_faircoin_address": user_faircoinaddress,
                                                   "email": email, "ocp_alias": alias}
                        # username = get_unique_username(key='ocp_id', value=user_id)
                        # if not username:
                        if _is_validated_comment(i['note']):
                            commitments[commitment_id]["pre_validators"].add(username)
                            continue
                        if i['action'] == "work" and i['start'] and 'affectedQuantity' in i:
                            date_str = i['start']
                            date = parse_date(date_str)

                            unit = i['affectedQuantity'].get('unit', None)
                            hours = i['affectedQuantity']["numericValue"]
                            if unit and (unit['name'] == 'Hour' or unit['name'] == 'Each') and hours > 0:
                                seconds_spent = hours * 3600

                                if i['requestDistribution']:
                                    contributors.add(username)
                                # if contribution not in this month, we ignore the time
                                if date_min > date or date_max < date:
                                    continue

                                title = ''
                                if i['note']:
                                    if len(i['note']) > 100:
                                        title = i['note'][:100] + u'…'
                                    else:
                                        title = i['note']

                                # Events are just informative to show in the popup window
                                if i['requestDistribution']:  # If not voluntary work
                                    if username not in process_work:
                                        process_work[username] = {commitment_id: {'seconds_spent': 0, 'events': []}}
                                    if commitment_id not in process_work[username]:
                                        process_work[username][commitment_id] = {'seconds_spent': 0, 'events': []}
                                    process_work[username][commitment_id]['seconds_spent'] += seconds_spent

                                    commitments[commitment_id]["contributors"].add(username)
                                    process_work[username][commitment_id]['events'].append({'date': date_str,
                                                                                            'seconds': seconds_spent,
                                                                                            'title': title})
                                else:
                                    if username not in voluntary_work:
                                        voluntary_work[username] = {'seconds_spent': 0, 'events': []}
                                    voluntary_work[username]['events'].append({'date': date_str,
                                                                               'seconds': seconds_spent,
                                                                               'title': title})
                                    voluntary_work[username]['seconds_spent'] += seconds_spent

                for commitment_id, commitment in commitments.items():
                    for username in commitment['pre_validators']:
                        # Requirement validation
                        commitments[commitment_id]["validators"].add(username)

                # Voluntary work
                for username, c in voluntary_work.items():
                    contributions.append({'id': p['id'],
                                          'type': 'OCP',
                                          'username': username,
                                          'date': None,
                                          'url': web_url,
                                          'is_voluntary': True,
                                          'validated': False,
                                          'validation_msgs': [],
                                          'task_title': p['name'],
                                          'events': c['events'],
                                          'total_time_spent': c['seconds_spent']})

                # Not Voluntary work
                for username, user_commitments in process_work.items():
                    for commitment_id, c in user_commitments.items():
                        c_validation_msgs = []
                        c_validated = False
                        c_validators = []

                        c_validators = commitments[commitment_id]["validators"].copy()
                        if username in c_validators:
                            c_validators.remove(username)
                        if len(c_validators):
                            c_validation_msgs.append('Commitment validated by: {0}'.format(
                                                     ", ".join(c_validators)))

                        total_validations = len(c_validators)
                        if total_validations >= 2:
                            c_validated = True
                        else:
                            c_validation_msgs.append('Still needs {0} commitment validation(s)'.format(
                                                     2 - total_validations))

                        contributions.append({'id': p['id'],
                                              'type': 'OCP',
                                              'username': username,
                                              'date': None,
                                              'url': web_url,
                                              'is_voluntary': False,
                                              'validated': c_validated,
                                              'validation_msgs': c_validation_msgs,
                                              'task_title': p['name'] + ' : ' + commitments[commitment_id]['title'],
                                              'events': c['events'],
                                              'total_time_spent': c['seconds_spent']})

        return contributions, ocp_users
