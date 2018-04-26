#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import requests
from dateutil.parser import parse
from slugify import slugify

from utils import get_unique_username
from validation import _is_validated_comment
logging.basicConfig(level=logging.DEBUG)

try:
    from env.settings import gitlab_token
except Exception:
    logging.error("gitlab_token not defined in env/settings.py, you should created it")

try:
    from env.settings import gitlab_host
except Exception:
    logging.error("gitlab_host not defined in env/settings.py, you should created it")


class GitlabConnector(object):
    server_users = {}
    server_users_emails = {}

    def get_server_users(self):
        all_users = []
        more_users = True
        page = 0
        while more_users:
            page += 1
            url = '{0}/v4/users/?page={1}&per_page=100'.format(gitlab_host, page)
            logging.debug(url)
            response = requests.get(url, headers={'PRIVATE-TOKEN': gitlab_token})
            more_users = response.json()
            all_users += more_users

        for user in all_users:
            username = user['username']
            email = user['email']
            self.server_users[username] = {'email': email, 'gitlab_id': user['id'],
                                           'location': user['location'],
                                           'gitlab_name': user['name'], 'gitlab_username': username}
            if email:
                self.server_users_emails[email] = username

    def filter_time_from_issue_notes(self, notes):
        pass
        # TODO: https://git.fairkom.net/api/v4/projects/12/issues/107/notes?per_page=100

    def get_labels(self, project_id):
        url = '{0}/v4/projects/{1}/labels/?per_page=100'.format(gitlab_host, project_id)
        response = requests.get(url, headers={'PRIVATE-TOKEN': gitlab_token})
        return response.json()

    def get_timestamp(self, project_id, issue_iid):
        url = '{0}/v4/projects/{1}/issues/{2}/time_stats'.format(gitlab_host, project_id, issue_iid)
        logging.debug(url)
        response = requests.get(url, headers={'PRIVATE-TOKEN': gitlab_token})
        return response.json()

    def get_comments(self, project_id, issue_iid):
        url = '{0}/v4/projects/{1}/issues/{2}/notes?per_page=100'.format(gitlab_host, project_id, issue_iid)
        logging.debug(url)
        response = requests.get(url, headers={'PRIVATE-TOKEN': gitlab_token})
        comments = []
        for c in response.json():
            comments.append((c['author']['username'], c['body']))
        return comments

    def get_issues(self, project_id=None):
        all_issues = []
        more = True
        page = 0
        while more:
            page += 1
            if project_id:
                url = '{0}/v4/projects/{1}/issues?state=opened&page={2}&per_page=100'.format(gitlab_host, project_id, page)
                logging.debug(url)
                response = requests.get(url, headers={'PRIVATE-TOKEN': gitlab_token})
                more = response.json()
                all_issues += more
        return all_issues

    def parse_issues(self, issues, project_id, date_min, date_max):
        # adding Gitlab tasks
        # project_labels = []
        contributions = []
        gitlab_users = {}
        for i in issues:
            # print("Issue", i['iid'])
            validators = set()
            wrong_validators = set()
            comments = []

            if 'COMPLETED' in i['labels'] or 'OCW VALIDATED' in i['labels']:
                # print('project_id', area['gitlab'], 'issue_iid', i['iid'])
                # print(i['title'], i['labels'])
                if len(i['assignees']) and i['time_stats']['total_time_spent'] > 0:
                    username = i['assignees'][0]['username']

                    email = self.server_users[username]['email']
                    # ocp_api_users_by_email[email]

                    # username = get_user_profile(self, gitlab_username=username)
                    user_profile = {"gitlab_username": username, 'email': email}
                    if self.server_users[username]['location'] and \
                       self.server_users[username]['location'].startswith('f'):
                        user_profile["gitlab_faircoin_address"] = self.server_users[username]['location']

                    if self.server_users[username]['gitlab_name']:
                        username = slugify(self.server_users[username]['gitlab_name']).replace("-", "_")

                    ocp_username = get_unique_username(key='gitlab', value=username)
                    if ocp_username:
                        user_profile["ocp_username"] = ocp_username
                        username = ocp_username

                    seconds_spent = i['time_stats']['total_time_spent']

                    due_date_str = i['due_date']
                    if due_date_str is not None:
                        due_date = parse(due_date_str)
                        if date_min > due_date or date_max < due_date:
                            continue

                    validation_msgs = []
                    validated = False
                    is_voluntary = False
                    if 'VOLUNTARY' in i['labels'] or '*VOLUNTARY' in i['labels']:
                        is_voluntary = True
                    else:
                        comments = self.get_comments(project_id=project_id, issue_iid=i['iid'])
                        for author, comment in comments:
                            if _is_validated_comment(comment):
                                if author != username:
                                    validators.add(author)
                                else:
                                    wrong_validators.add(author)

                        if len(validators):
                            validation_msgs.append('Validated by: {0}'.format(", ".join(validators)))
                        if len(wrong_validators):
                            validation_msgs.append('Invalid selfvalidations by: {0}'.format(
                                                   ", ".join(wrong_validators)))
                        if len(validators) >= 2:
                            validated = True
                        else:
                            validation_msgs.append('Still needs {0} validation(s)'.format(2 - len(validators)))

                    if due_date_str is None:
                        validated = False
                        validation_msgs.append('Due date not specified')

                    gitlab_users[username] = user_profile
                    contributions.append({'id': i['iid'],
                                          'type': 'GITLAB',
                                          'date': due_date_str,
                                          'url': i['web_url'],
                                          'is_voluntary': is_voluntary,
                                          'validated': validated,
                                          'validation_msgs': validation_msgs,
                                          'task_title': i['title'],
                                          'total_time_spent': seconds_spent,
                                          'username': username})

        return contributions, gitlab_users
