"""Idempotently register the three local chat choices without credentials."""
import copy
import json
import subprocess

deepseek = {'model': 'deepseek-v4.1-flash', 'max_tokens': 16384,
            'extra_body': {'thinking': {'type': 'disabled'}},
            'price': {'input': .30, 'output': 1.20, 'cache_read': .006}}
glm = {'model': 'glm-5.3-flash', 'max_tokens': 16384,
       'extra_body': {'reasoning_effort': 'low'},
       'price': {'input': .15, 'output': .50, 'cache_read': .03}}
muse = {'model': 'muse-spark-1.3-contributor', 'max_tokens': 16384,
        'reasoning': {'effort': 'low'}, 'price': {'input': .10, 'output': .20, 'cache_read': .002}}
roles = ['simple', 'simple_json', 'primary_agent', 'assistant', 'generator', 'refiner',
         'adviser', 'reflector', 'searcher', 'enricher', 'coder', 'installer', 'pentester']
base = {role: copy.deepcopy(muse if role in {'generator', 'refiner', 'coder'} else
                           glm if role in {'adviser', 'pentester'} else deepseek) for role in roles}
base['simple_json']['json'] = True
statements = ['BEGIN;']
for name, selected in [('DeepSeek V4.1 Flash', deepseek), ('GLM 5.3 Flash', glm),
                       ('Muse Spark 1.3 Contributor', muse)]:
    config = copy.deepcopy(base)
    config['assistant'] = selected
    encoded = json.dumps(config).encode().hex()
    statements.append(f"INSERT INTO providers (user_id,type,name,config) SELECT id,'custom','{name}',convert_from(decode('{encoded}','hex'),'UTF8')::json FROM users WHERE id=1 ON CONFLICT (name,user_id) WHERE deleted_at IS NULL DO NOTHING;")
statements += ['COMMIT;', 'SELECT id,name,type FROM providers WHERE deleted_at IS NULL;']
subprocess.run(['docker', 'exec', '-i', 'pgvector', 'psql', '-U', 'postgres', '-d', 'pentagidb', '-v', 'ON_ERROR_STOP=1'],
               input='\n'.join(statements), text=True, check=True)
