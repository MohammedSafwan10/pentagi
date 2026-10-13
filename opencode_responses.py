"""Translate PentAGI Chat Completions to Muse's Responses protocol."""
import json
import time


def to_responses(chat):
    if chat.get('n', 1) != 1:
        raise ValueError('Muse supports one completion per request')
    items = []
    for message in chat.get('messages', []):
        role = message['role']
        content = message.get('content')
        if role == 'tool':
            items.append({'type': 'function_call_output', 'call_id': message['tool_call_id'],
                          'output': content if isinstance(content, str) else json.dumps(content)})
            continue
        if role not in {'user', 'assistant', 'system', 'developer'}:
            raise ValueError(f'Unsupported message role: {role}')
        if content:
            if isinstance(content, list):
                parts = []
                for part in content:
                    if part['type'] == 'text':
                        parts.append({'type': 'output_text' if role == 'assistant' else 'input_text',
                                      'text': part['text']})
                    elif part['type'] == 'image_url' and role == 'user':
                        parts.append({'type': 'input_image', **part['image_url']})
                        parts[-1]['image_url'] = parts[-1].pop('url')
                    else:
                        raise ValueError(f"Unsupported content type: {part['type']}")
                content = parts
            items.append({'role': role, 'content': content})
        for call in message.get('tool_calls', []):
            items.append({'type': 'function_call', 'call_id': call['id'],
                          'name': call['function']['name'], 'arguments': call['function']['arguments']})
    result = {'model': chat['model'], 'input': items, 'stream': bool(chat.get('stream')), 'store': False}
    for key in ('temperature', 'top_p', 'parallel_tool_calls'):
        if key in chat:
            result[key] = chat[key]
    limit = chat.get('max_completion_tokens', chat.get('max_tokens'))
    if limit is not None:
        result['max_output_tokens'] = limit
    if chat.get('reasoning_effort'):
        result['reasoning'] = {'effort': chat['reasoning_effort'], 'summary': 'auto'}
    if chat.get('tools'):
        result['tools'] = []
        for tool in chat['tools']:
            if tool['type'] != 'function':
                raise ValueError('Only function tools can be translated')
            result['tools'].append({'type': 'function', **tool['function']})
    choice = chat.get('tool_choice')
    if choice is not None:
        if choice != 'auto':
            raise ValueError('Muse currently supports only automatic tool selection')
        result['tool_choice'] = choice
    fmt = chat.get('response_format')
    if fmt:
        if fmt['type'] == 'json_schema':
            fmt = {'type': 'json_schema', **fmt['json_schema']}
        result['text'] = {'format': fmt}
    return result


def usage(data):
    value = data.get('usage') or {}
    return {'prompt_tokens': value.get('input_tokens', 0),
            'completion_tokens': value.get('output_tokens', 0),
            'total_tokens': value.get('total_tokens', 0),
            'prompt_tokens_details': value.get('input_tokens_details', {}),
            'completion_tokens_details': value.get('output_tokens_details', {})}


def to_chat(data, model):
    if data.get('error') or data.get('status') in {'failed', 'cancelled'}:
        raise ValueError((data.get('error') or {}).get('message', 'Muse response failed'))
    text, calls, thinking = '', [], ''
    for item in data.get('output', []):
        if item['type'] == 'message':
            for part in item.get('content', []):
                if part['type'] == 'output_text':
                    text += part['text']
                elif part['type'] == 'refusal':
                    text += part['refusal']
        elif item['type'] == 'reasoning':
            thinking += ''.join(part.get('text', '') for part in item.get('summary', []) if part.get('type') == 'summary_text')
        elif item['type'] == 'function_call':
            calls.append({'id': item['call_id'], 'type': 'function',
                          'function': {'name': item['name'], 'arguments': item['arguments']}})
    message = {'role': 'assistant', 'content': text or None}
    if thinking:
        message['reasoning_content'] = thinking
    if calls:
        message['tool_calls'] = calls
    reason = 'length' if data.get('status') == 'incomplete' else 'tool_calls' if calls else 'stop'
    return {'id': data.get('id', 'chatcmpl-muse'), 'object': 'chat.completion',
            'created': data.get('created_at', int(time.time())), 'model': model,
            'choices': [{'index': 0, 'message': message, 'finish_reason': reason}], 'usage': usage(data)}


def events(response):
    """Decode SSE frames, including multiline data frames."""
    lines = []
    for line in response:
        line = line.decode('utf-8').rstrip('\r\n')
        if not line:
            if lines:
                data = '\n'.join(lines)
                if data != '[DONE]':
                    yield json.loads(data)
            lines = []
        elif line.startswith('data:'):
            lines.append(line[5:].lstrip())
    if lines and '\n'.join(lines) != '[DONE]':
        yield json.loads('\n'.join(lines))


def chat_chunks(response, model):
    identity = {'id': 'chatcmpl-muse', 'object': 'chat.completion.chunk',
                'created': int(time.time()), 'model': model}
    tools = {}
    completed = False
    for event in events(response):
        kind = event.get('type')
        delta, finish, tokens = None, None, None
        if kind == 'response.created':
            identity['id'] = event['response']['id']
            identity['created'] = event['response'].get('created_at', identity['created'])
            delta = {'role': 'assistant'}
        elif kind in {'response.reasoning_summary_text.delta', 'response.reasoning_text.delta'}:
            delta = {'reasoning_content': event['delta']}
        elif kind == 'response.output_text.delta':
            delta = {'content': event['delta']}
        elif kind == 'response.refusal.delta':
            delta = {'content': event['delta']}
        elif kind == 'response.output_item.added' and event['item']['type'] == 'function_call':
            item = event['item']
            index = len(tools)
            tools[event['output_index']] = index
            delta = {'tool_calls': [{'index': index, 'id': item['call_id'], 'type': 'function',
                                    'function': {'name': item['name'], 'arguments': item.get('arguments', '')}}]}
        elif kind == 'response.function_call_arguments.delta':
            delta = {'tool_calls': [{'index': tools[event['output_index']],
                                    'function': {'arguments': event['delta']}}]}
        elif kind in {'response.completed', 'response.incomplete'}:
            data = event['response']
            if data.get('error'):
                raise ValueError(data['error'].get('message', 'Muse response failed'))
            finish = 'length' if kind == 'response.incomplete' else 'tool_calls' if tools else 'stop'
            delta, tokens, completed = {}, usage(data), True
        elif kind in {'response.failed', 'error'}:
            error = event.get('error') or event.get('response', {}).get('error') or event
            raise ValueError(error.get('message', 'Muse stream failed'))
        if delta is not None:
            chunk = {**identity, 'choices': [{'index': 0, 'delta': delta, 'finish_reason': finish}]}
            if tokens is not None:
                chunk['usage'] = tokens
            yield chunk
            if completed:
                return
    if not completed:
        raise ValueError('Muse stream ended without a completion event')
