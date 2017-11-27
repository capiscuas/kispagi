#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import requests
from dateutil.parser import parse

from utils import _is_validated_comment, get_unique_username
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
        if project_id:
            url = '{0}/v4/projects/{1}/issues?state=opened&per_page=100'.format(gitlab_host, project_id)
            logging.debug(url)
            response = requests.get(url, headers={'PRIVATE-TOKEN': gitlab_token})
            return response.json()
        return None

    def parse_issues(self, issues, project_id, date_min, date_max):
        # adding Gitlab tasks
        # project_labels = []
        contributions = []
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
                    username = get_unique_username(key='gitlab', value=username)
                    seconds_spent = i['time_stats']['total_time_spent']
                    comments = self.get_comments(project_id=project_id, issue_iid=i['iid'])
                    validation_msgs = []
                    validated = False
                    is_voluntary = False
                    due_date_str = i['due_date']
                    if due_date_str is not None:
                        due_date = parse(due_date_str)
                        if date_min > due_date or date_max < due_date:
                            continue

                    if 'VOLUNTARY' in i['labels'] or '*VOLUNTARY' in i['labels']:
                        is_voluntary = True
                    else:
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

                    contributions.append({'id': i['iid'],
                                          'type': 'GITLAB',
                                          'date': due_date_str,
                                          'url': i['web_url'],
                                          'is_voluntary': is_voluntary,
                                          'validated': validated,
                                          'validation_msgs': validation_msgs,
                                          'task_title': "{0}".format(i['title']),
                                          'total_time_spent': seconds_spent,
                                          'username': username})
        return contributions
