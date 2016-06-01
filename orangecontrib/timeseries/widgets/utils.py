
def available_name(domain, template):
    """Return the next available variable name (from template) that is not
    already taken in domain"""
    for i in range(1000):
        name = '{}{}'.format(template, ' ({})'.format(i) if i else '')
        if name not in domain:
            return name
