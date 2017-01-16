import json
import os
import six
import pprint

apiConfig = None
with open('apis.json') as f:
    apiConfig = json.load(f)


def cleanDocstring(old, indent=0):
    new = old.replace('"""', '\"\"\"')
    new = new.replace('\'\'\'', '\\\'\\\'\\\'')
    new = new.split('\n')
    new.insert(0, '"""')
    new.append('"""')
    # Basically this comprehension is so we don't get empty lines...
    new = [' ' * indent + x if x.strip() != '' else '' for x in new]
    return '\n'.join(new)


def createStaticClient(name, api):
    api = api['reference']

    docstring = api.get('description')

    # Generate the first part of the class, basically just import the BaseClient
    # class
    lines = [
        '# coding=utf-8',
        '#####################################################',
        '# THIS FILE IS AUTOMATICALLY GENERATED. DO NOT EDIT #',
        '#####################################################',
        '# noqa: E128,E201'
        '',
        'from .client import BaseClient, createTemporaryCredentials, config, createApiClient',
        '_defaultConfig = config',
        '',
        '',
    ]

    lines.append('class %s(BaseClient):' % name)

    # If the API has a description, we'll make that be the docstring.  We want
    # to process the docstring so that it's a """ string in Python with the
    # correct indentation.  Also escape triple quotes so that it's not easy
    # to break out of the docstring accidentally
    if docstring:
        lines.append(cleanDocstring(docstring, indent=4))

    lines.append('    classOptions = {')

    copiedOptions = ('baseUrl', 'exchangePrefix')
    for opt in copiedOptions:
        if api.get(opt):
            lines.append('        "%s": "%s"' % (opt, api[opt]))
    
    lines.extend(['    }', ''])

    # We need to build up some information about how the functions work
    functionInfo = {}

    for entry in api['entries']:
        if entry['type'] == 'function':
            # We don't want to burn in the full api reference for each thing as
            # the dictionary parameter, since we'll be using some of these for
            # the code formatting (e.g. docstring)
            #
            # Sometimes, mandatory fields are hardcoded at declaration and
            # optional are copied in with a loop
            funcRef = {
                'args': entry['args'],
                'name': entry['name'],
                'route': entry['route'],
                'method': entry['method'],
            }
            for key in ['stability', 'query', 'input', 'output']:
                if (entry.get(key)):
                    funcRef[key] = entry[key]

            functionInfo[entry['name']] = funcRef

            # Let's genereate a docstring, but only if it's got some meat
            if entry.get('description'):
                ds = entry.get('description', '')
                if entry.get('title'):
                    ds = entry.get('title') + '\n\n' + ds
                if entry.get('input'):
                    ds = '%s\n\nThis method takes input: ``%s``' % (ds, entry['input'])
                if entry.get('output'):
                    ds = '%s\n\nThis method takes output: ``%s``' % (ds, entry['output'])
                if entry.get('stability'):
                    ds = '%s\n\nThis method is ``%s``' % (ds, entry['stability'])

                lines.append(cleanDocstring(ds, indent=4))

            lines.extend([
                '    def %s(self, *args, **kwargs):' % entry['name'],
                '        return self._makeApiCall(self.funcinfo["%s"], *args, **kwargs)' % entry['name'],
                ''
            ])
        elif entry['type'] == 'topic-exchange':
            # We don't want to burn in the full api reference for each thing as
            # the dictionary parameter, since we'll be using some of these for
            # the code formatting (e.g. docstring)
            #
            # Sometimes, mandatory fields are hardcoded at declaration and
            # optional are copied in with a loop
            exRef = {
                'exchange': entry['exchange'],
                'name': entry['name'],
                'routingKey': entry['routingKey'],
            }
            for key in ['schema']:
                if (entry.get(key)):
                    exRef[key] = entry[key]

            # Let's genereate a docstring, but only if it's got some meat
            if entry.get('description'):
                ds = entry.get('description', '')
                if entry.get('title'):
                    ds = entry.get('title') + '\n\n' + ds
                if entry.get('schema'):
                    ds = '%s\n\nThis exchange outputs: ``%s``' % (ds, entry['schema'])
                if entry.get('stability'):
                    ds = '%s\n\nThis method is ``%s``' % (ds, entry['stability'])

                ds += 'This exchange takes the following keys:'
                for key in entry['routingKey']:
                    ds += '\n\n * %s: %s%s' % (key.get('name'), key.get('summary', ''), ' (required)' if key['required'] else '')

                lines.append(cleanDocstring(ds, indent=4))

            lines.extend([
                '    def %s(self, *args, **kwargs):' % entry['name'],
                '        return self._makeTopicExchange(%s, *args, **kwargs)' % repr(exRef),
                ''
            ])


    lines.append('    funcinfo = {')
    for funcname, ref in functionInfo.items():
        lines.append('        "%s": %s,' % (funcname, pprint.pformat(ref, indent=12)))
    lines.append('    }')

    lines.extend([
        '',
        '',
        '__all__ = %s' % repr([
            'createTemporaryCredentials',
            'config',
            '_defaultConfig',
            'createApiClient',
            name
        ]),
        '',
    ]) 

    # Join the lines, then re-split them because some embedded new lines need
    # to be addressed
    lines = '\n'.join(lines)
    lines = lines.split('\n')

    # Clean up trailing whitespace
    lines = [x.rstrip() for x in lines]

    # Build the final string
    return '\n'.join(lines)
    

filesCreated = []
importerLines = []
for name, api in apiConfig.items():
    filename = os.path.join('taskcluster', name.lower() + '.py')
    clientString = createStaticClient(name, api)
    importerLines.append('from .%s import %s  # NOQA' % (name.lower(), name))
    with open(filename, 'w') as f:
        if six.PY2:
            f.write(clientString.encode('utf-8'))
        else:
            f.write(clientString)
        filesCreated.append(filename)

with open(os.path.join('taskcluster', '_client_importer.py'), 'w') as f:
    importerLines.append('')
    filesCreated.append(os.path.join('taskcluster', '_client_importer.py'))
    f.write('\n'.join(importerLines))

with open('filescreated.dat', 'w') as f:
    f.write('\n'.join(filesCreated))
