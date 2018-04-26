from collections import defaultdict
import validation


def default_contribution():
    return {'total_time_spent': 0, 'events': []}


def defaultdict_user_contributions():
    return defaultdict(default_contribution)


def filter_by_remuneration(contributions):
    remunerated_work = defaultdict(defaultdict_user_contributions)
    voluntary_work = defaultdict(defaultdict_user_contributions)

    for c in contributions:
        username = c['username']
        contribution_id = c['id']
        seconds_spent = c.pop('total_time_spent')
        time_entry = {'date': c['date'], 'seconds': seconds_spent,  'title': c['task_comments']}
        if not c['is_voluntary']:  # If remunerated_work
            remunerated_work[username][contribution_id].update(c)
            remunerated_work[username][contribution_id]['total_time_spent'] += seconds_spent
            remunerated_work[username][contribution_id]['events'].append(time_entry)
        else:
            voluntary_work[username][contribution_id].update(c)
            voluntary_work[username][contribution_id]['total_time_spent'] += seconds_spent
            voluntary_work[username][contribution_id]['events'].append(time_entry)
    return remunerated_work, voluntary_work


def validate_remunerations(remunerated_work):
    for username, user_commitments in remunerated_work.items():
        for commitment_id, c in user_commitments.items():
                validations = c.get("validations", [])
                c_validated, c_validation_msgs = validation.calculate(username, validations)
                c['validated'] = c_validated
                c['validation_msgs'] = c_validation_msgs
    return remunerated_work
