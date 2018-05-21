#!/usr/bin/env python
# -*- coding: utf-8 -*-

import flask
import pickle
from werkzeug.contrib.atom import AtomFeed
from datetime import datetime


def generate_feed():
    feed = AtomFeed('Kispagi OCW Recent Changes',
                    feed_url=flask.request.url, url=flask.request.url_root,
                    icon='http://kispagi.fair.coop/static/logo.png')

    try:
        notifications = pickle.load(open('/tmp/last_notifications.p', "rb"))
    except:
        notifications = []

    for n in notifications:
        timestamp = (n.when - datetime(1970, 1, 1)).total_seconds()
        feed.add(n.title, n.content,
                 content_type='html',
                 author=n.author,
                 id=str(timestamp),
                 url=n.url,
                 updated=n.when)
    return feed.get_response()


class Notification(object):
    author = ""
    title = ""
    when = None
    content = ""
    url = ""

    def __init__(self, author, title, when, content, url):
        self.author = author
        self.title = title
        self.when = when
        self.content = content
        self.url = url


def new_notif(event, action_msg):
    username = event['username']
    area_name = event['area_name']
    event_comments = event['task_comments']
    task_title = event['task_title']
    url = event['url']

    n_title = u'{} {} in project {}. Comment: {}'.format(username, action_msg, area_name, event_comments)
    n_content = u'Issue: {}'.format(task_title)
    return Notification(author=username, title=n_title, when=datetime.now(), content=n_content, url=url)


def check_time_event_changes(new, old):
    if not old:
        return

    try:
        notifications = pickle.load(open('/tmp/last_notifications.p', "rb"))
    except:
        notifications = []

    new_events_dict = {}
    old_events_dict = {}
    for event in new:
        key = event['time_event_id']
        new_events_dict[key] = event
    for event in old:
        key = event['time_event_id']
        old_events_dict[key] = event

    # Comparing new events with old ones
    for id, event in new_events_dict.items():
        total_hours_spent = event['total_time_spent'] / 3600
        voluntary_adj = 'voluntary' if event['is_voluntary'] else 'non voluntary'
        if id in old_events_dict:
            old_event = old_events_dict[id]
            old_total_hours_spent = old_event['total_time_spent'] / 3600
            old_voluntary_adj = 'voluntary' if old_event['is_voluntary'] else 'non voluntary'
            if total_hours_spent != old_total_hours_spent or voluntary_adj != old_voluntary_adj:
                notifications.append(new_notif(event, u'changed from {} {} hours to {} {} hours'.format(old_total_hours_spent, old_voluntary_adj,
                                                                                                       total_hours_spent, voluntary_adj)))
        else:
            notifications.append(new_notif(event, u'added {} {} hours'.format(total_hours_spent, voluntary_adj)))

    # Comparing old events with new ones
    for id, event in old_events_dict.items():
        total_hours_spent = event['total_time_spent'] / 3600
        voluntary_adj = 'voluntary' if event['is_voluntary'] else 'non voluntary'
        if id not in new_events_dict:
            notifications.append(new_notif(event, u'removed its {} {} hours'.format(total_hours_spent, voluntary_adj)))

    pickle.dump(notifications[:60], open('/tmp/last_notifications.p', "wb"))
