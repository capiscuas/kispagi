#!/usr/bin/env python
# -*- coding: utf-8 -*-

from collections import defaultdict
import os.path
import requests


from dateutil.parser import parse as parse_date
from datetime import timedelta
from slugify import slugify
import json
import logging

import validation
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
    parent = None

    def __init__(self, parent):
        self.parent = parent

    def getUserDetails(self, user_id, user_fullname):
        alias = None
        email = None
        ocp_slug_username = slugify(user_fullname).replace("-", "_")
        if int(user_id) in self.server_agent2email:
            email = self.server_agent2email[int(user_id)]
            if email in self.server_email2username:
                alias = self.server_email2username[email]

        # gitlab_username = self.parent.gitlab.server_users_emails.get(email, None)
        # if gitlab_username:
        #     username = gitlab_username
        # else:
        username = ocp_slug_username
        return username, email, alias

    def get_server_users(self):
        users2emails = {}

        with open(os.path.join(self.parent.dir_path, 'env', 'ocp.users.json')) as data_file:
            data = json.load(data_file)

        for user in data:
            email = user['email']
            users2emails[user['api_url']] = email
            self.server_email2username[email] = user['username']

        with open(os.path.join(self.parent.dir_path, 'env', 'ocp.agents.json')) as data_file:
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
                              validations { id validationDate validatedBy { id name } }
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
            raise

        return None

    def parse_issues(self, issues, area_name, project_id, date_min, date_max):
        contributions = []
        processes = issues["data"]["viewer"]["agent"]["agentProcesses"]

        ocp_users = {}
        for p in processes:
            # Deprecated web_url = 'https://ocp.freedomcoop.eu/work/process-logging/{0}/'.format(p['id'])

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
                        if w_id not in inputs:
                            continue
                        i = inputs[w_id]

                        user_fullname = i['provider']['name']
                        user_id = i['provider']['id']
                        username, email, alias = self.getUserDetails(user_id, user_fullname)

                        if username not in ocp_users:
                            user_faircoinaddress = i['provider']['faircoinAddress']
                            ocp_users[username] = {"ocp_username": username, "ocp_id": user_id,
                                                   "faircoin_address": user_faircoinaddress,
                                                   "email": email, "ocp_alias": alias}

                        if validation._is_validated_comment(i['note']):
                            commitments[commitment_id]["pre_validators"].add(username)
                            continue
                        if i['action'] == "work" and i['start'] and 'affectedQuantity' in i:
                            date_str = i['start']
                            date = parse_date(date_str)

                            unit = i['affectedQuantity'].get('unit', None)
                            hours = i['affectedQuantity']["numericValue"]
                            if unit and (unit['name'] == 'Hour' or unit['name'] == 'Each') and hours > 0:
                                seconds_spent = hours * 3600

                                # if contribution not in this month, we ignore the time
                                if date_min > date or date_max < date:
                                    continue

                                validations = i.get('validations', [])
                                kispagi_validations = []
                                for v in validations:
                                    validator, email, alias = self.getUserDetails(v['validatedBy']["id"], v['validatedBy']["name"])
                                    validation_date = parse_date(v['validationDate'])
                                    kispagi_validations.append({'validator': validator, 'date': validation_date})

                                c_title = commitments[commitment_id]['title']
                                event_id = i['id']
                                event_title = i.get('note', '')
                                web_url = 'https://agent.fair.coop/#/validate/event/{0}'.format(event_id)
                                contributions.append({'id': event_id,
                                                      'type': 'OCP',
                                                      'date': date_str,
                                                      'url': web_url,
                                                      'is_voluntary': not i['requestDistribution'],
                                                      'validations': kispagi_validations,
                                                      'validation_msgs': [],
                                                      'validated': False,
                                                      'area_name': area_name,
                                                      'time_event_id': event_id,
                                                      'task_title': u'{}:{}'.format(p['name'], c_title),
                                                      'task_comments': event_title,
                                                      'total_time_spent': seconds_spent,
                                                      'username': username})


        return contributions, ocp_users
