import { describe, expect, it } from 'vitest';

import type { AssistantLogFragmentFragment } from '@/graphql/types';

import { MessageLogType } from '@/graphql/types';

import { buildAssistantHandoff } from './assistant-handoff';

const log = (type: MessageLogType, message: string) => ({ message, type }) as AssistantLogFragmentFragment;

describe('switching an assistant model', () => {
    it('carries conversation turns in order without replaying tool output', () => {
        const result = buildAssistantHandoff(
            [
                log(MessageLogType.Input, 'Remember 42'),
                log(MessageLogType.Terminal, 'secret tool output'),
                log(MessageLogType.Answer, 'I remember 42'),
            ],
            'What number?',
        );
        expect(result).toContain('Remember 42');
        expect(result).toContain('I remember 42');
        expect(result).not.toContain('secret tool output');
        expect(result.indexOf('Remember 42')).toBeLessThan(result.indexOf('I remember 42'));
        expect(result.endsWith('What number?')).toBe(true);
    });

    it('bounds old context while preserving the entire new message', () => {
        const result = buildAssistantHandoff([log(MessageLogType.Input, 'x'.repeat(50_000))], 'Current request');
        expect(result.length).toBeLessThan(25_000);
        expect(result.endsWith('Current request')).toBe(true);
    });

    it('sends a new message directly when there is no old conversation', () => {
        expect(buildAssistantHandoff([], 'Hello')).toBe('Hello');
    });
});
