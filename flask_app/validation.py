def calculate(username, validations):
    c_validation_msgs = []
    c_validated = False
    if len(validations) and type(list(validations)[0]) == str:
        c_validators = [x for x in validations]
    else:
        c_validators = [x['validator'] for x in validations]

    if username in c_validators:
        c_validators.remove(username)
    if len(c_validators):
        c_validation_msgs.append('Work validated by: {0}'.format(
                                 ", ".join(c_validators)))

    total_validations = len(c_validators)
    if total_validations >= 2:
        c_validated = True
    else:
        c_validation_msgs.append('Still needs {0} work validation(s)'.format(
                                 2 - total_validations))

    return c_validated, c_validation_msgs

validated_strings = ['VALIDATED', 'VLIDATED', 'VALIDATE', 'VALIDADO', 'VALIDATD', 'VLALIDATED']


def _is_validated_status(details):
    VALIDATED_STATUSES = ['7', '8']  # those are the status VALIDATED and VALIDATED+ that can alternate
    for d in details:
        if 'name' in d and d['name'] == 'status_id' and 'new_value' in d and d['new_value'] in VALIDATED_STATUSES:
            return True
    return False


def _is_validated_comment(comment):
    return 'VALIDATED' in comment.upper()
    #     comment = comment.replace("#", "").replace(".", "").replace(",", "").replace("<p>", "").replace("</p>", "").strip()
    #     if comment.split():
    #         first_word = comment.split()[0]
    #         return first_word.upper() in validated_strings
    #
    # return False
