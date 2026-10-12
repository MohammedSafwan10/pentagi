"""Harmless live tool-call/streaming checks; credentials stay out of output."""
import json
import subprocess

info = json.loads(subprocess.check_output(['docker', 'inspect', 'pentagi']))[0]
env = dict(value.split('=', 1) for value in info['Config']['Env'])
script = r'''
import json, urllib.request, urllib.error
KEY = __KEY__
def call(body):
    req = urllib.request.Request('http://127.0.0.1:8080/zen/go/v1/chat/completions', data=json.dumps(body).encode(), headers={'Authorization':'Bearer '+KEY,'Content-Type':'application/json','x-opencode-session':'pentagi-bridge-verification'})
    try:
        return urllib.request.urlopen(req, timeout=120)
    except urllib.error.HTTPError as error:
        print('Upstream error:', error.code, error.read().decode()[:1000])
        raise
tool={'type':'function','function':{'name':'add','description':'Add two numbers','parameters':{'type':'object','properties':{'a':{'type':'integer'},'b':{'type':'integer'}},'required':['a','b'],'additionalProperties':False}}}
messages=[{'role':'user','content':'Use add to calculate 2+3. After the tool result, reply with the result only.'}]
body={'model':'muse-spark-1.3-contributor','messages':messages,'tools':[tool],'tool_choice':'auto','max_tokens':4096,'reasoning_effort':'low'}
with call(body) as r:
    data=json.load(r)
message=data['choices'][0]['message']
assert message.get('tool_calls'), data
tool_call=message['tool_calls'][0]
args=json.loads(tool_call['function']['arguments'])
assert args=={'a':2,'b':3}, args
print('Muse nonstream function call: PASS')
messages += [message, {'role':'tool','tool_call_id':tool_call['id'],'content':'5'}]
body.update(messages=messages,tool_choice='auto',stream=True)
content=''; finished=False
with call(body) as r:
    for line in r:
        if line.startswith(b'data: ') and b'[DONE]' not in line:
            item=json.loads(line[6:])
            assert 'error' not in item, item
            for choice in item.get('choices',[]):
                content += choice.get('delta',{}).get('content') or ''
                finished = finished or choice.get('finish_reason')=='stop'
assert finished and '5' in content, content
print('Muse streamed tool-result follow-up: PASS:',content)
'''.replace('__KEY__', json.dumps(env['LLM_SERVER_KEY']))
result = subprocess.run(['docker', 'exec', '-i', 'opencode-proxy', 'python', '-'], input=script, text=True)
raise SystemExit(result.returncode)
