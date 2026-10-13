import io
import json
import unittest

from opencode_responses import chat_chunks, to_chat, to_responses


def stream(*events):
    return io.BytesIO(b''.join(('data: ' + json.dumps(e) + '\n\n').encode() for e in events))


class BridgeTests(unittest.TestCase):
    def test_terminal_event_does_not_wait_for_connection_to_close(self):
        class KeepAliveStream:
            def __iter__(self):
                yield b'data: {"type":"response.completed","response":{}}\n'
                yield b'\n'
                raise AssertionError('bridge read past the terminal event')
        self.assertEqual(len(list(chat_chunks(KeepAliveStream(), 'muse'))), 1)

    def test_reasoning_summary_streams_separately_from_answer(self):
        chunks = list(chat_chunks(stream(
            {'type': 'response.reasoning_summary_text.delta', 'delta': 'Checking the calculation'},
            {'type': 'response.output_text.delta', 'delta': '5'},
            {'type': 'response.completed', 'response': {}}), 'muse'))
        self.assertEqual(chunks[0]['choices'][0]['delta'], {'reasoning_content': 'Checking the calculation'})
        self.assertEqual(chunks[1]['choices'][0]['delta'], {'content': '5'})
        result = to_chat({'output': [{'type': 'reasoning', 'summary': [{'type': 'summary_text', 'text': 'Checked'}]}]}, 'muse')
        self.assertEqual(result['choices'][0]['message']['reasoning_content'], 'Checked')

    def test_tool_history_and_definitions_are_converted(self):
        result = to_responses({'model': 'muse', 'messages': [
            {'role': 'system', 'content': 'Help'},
            {'role': 'assistant', 'content': None, 'tool_calls': [
                {'id': 'call_1', 'function': {'name': 'add', 'arguments': '{"a":1}'}}]},
            {'role': 'tool', 'tool_call_id': 'call_1', 'content': '2'}],
            'tools': [{'type': 'function', 'function': {'name': 'add', 'parameters': {'type': 'object'}}}],
            'tool_choice': 'auto',
            'max_tokens': 8192, 'response_format': {'type': 'json_schema', 'json_schema': {'name': 'result', 'schema': {'type': 'object'}}}})
        self.assertEqual(result['input'][1]['type'], 'function_call')
        self.assertEqual(result['input'][2]['call_id'], 'call_1')
        self.assertEqual(result['tools'][0]['name'], 'add')
        self.assertEqual(result['tool_choice'], 'auto')
        self.assertEqual(result['max_output_tokens'], 8192)
        self.assertEqual(result['text']['format']['name'], 'result')

    def test_incomplete_is_not_reported_as_successful_stop(self):
        result = to_chat({'status': 'incomplete', 'output': [], 'usage': {'input_tokens': 1, 'output_tokens': 2, 'total_tokens': 3}}, 'muse')
        self.assertEqual(result['choices'][0]['finish_reason'], 'length')
        self.assertEqual(result['usage']['total_tokens'], 3)

    def test_streaming_tool_calls_use_dense_indexes(self):
        chunks = list(chat_chunks(stream(
            {'type': 'response.created', 'response': {'id': 'resp_1'}},
            {'type': 'response.output_item.added', 'output_index': 2,
             'item': {'type': 'function_call', 'call_id': 'call_1', 'name': 'add', 'arguments': ''}},
            {'type': 'response.function_call_arguments.delta', 'output_index': 2, 'delta': '{"a":1}'},
            {'type': 'response.completed', 'response': {'usage': {'total_tokens': 3}}}), 'muse'))
        self.assertEqual(chunks[1]['choices'][0]['delta']['tool_calls'][0]['index'], 0)
        self.assertEqual(chunks[2]['choices'][0]['delta']['tool_calls'][0]['function']['arguments'], '{"a":1}')
        self.assertEqual(chunks[-1]['choices'][0]['finish_reason'], 'tool_calls')

    def test_stream_forwards_text_before_completion(self):
        chunks = chat_chunks(stream(
            {'type': 'response.output_text.delta', 'delta': 'hello'},
            {'type': 'response.completed', 'response': {}}), 'muse')
        self.assertEqual(next(chunks)['choices'][0]['delta']['content'], 'hello')
        self.assertEqual(next(chunks)['choices'][0]['finish_reason'], 'stop')

    def test_failed_or_truncated_stream_is_an_error(self):
        with self.assertRaises(ValueError):
            list(chat_chunks(stream({'type': 'response.failed', 'response': {'error': {'message': 'bad'}}}), 'muse'))
        with self.assertRaises(ValueError):
            list(chat_chunks(stream({'type': 'response.output_text.delta', 'delta': 'partial'}), 'muse'))

    def test_images_use_responses_content_types(self):
        result = to_responses({'model': 'muse', 'messages': [{'role': 'user', 'content': [
            {'type': 'text', 'text': 'Describe'}, {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,AA==', 'detail': 'low'}}]}]})
        self.assertEqual(result['input'][0]['content'][1]['type'], 'input_image')

    def test_unsupported_tool_choice_is_not_silently_changed(self):
        with self.assertRaisesRegex(ValueError, 'automatic'):
            to_responses({'model': 'muse', 'messages': [], 'tool_choice': 'required'})


if __name__ == '__main__':
    unittest.main()
