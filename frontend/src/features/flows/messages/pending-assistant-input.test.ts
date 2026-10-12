import { act, renderHook } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { AssistantLogFragmentFragment } from '@/graphql/types';

import { MessageLogType } from '@/graphql/types';

import { assignPendingInput, beginPendingInput, removePendingInput, usePendingInputs } from './pending-assistant-input';

describe('immediate assistant input feedback', () => {
    it('shows a message before setup and keeps it after the assistant ID arrives', () => {
        const { rerender, result } = renderHook(
            ({ assistantId }: { assistantId: null | string }) => usePendingInputs('optimistic-flow', assistantId, []),
            { initialProps: { assistantId: null } as { assistantId: null | string } },
        );
        let id = '';
        act(() => {
            id = beginPendingInput('optimistic-flow', null, 'Hello');
        });
        expect(result.current[0]?.message).toBe('Hello');
        act(() => assignPendingInput(id, 'optimistic-flow', '42'));
        rerender({ assistantId: '42' });
        expect(result.current[0]?.message).toBe('Hello');
        act(() => removePendingInput(id));
        expect(result.current).toHaveLength(0);
    });

    it('does not confuse a repeated message with an older saved copy', () => {
        const saved = {
            assistantId: '42',
            id: 'old',
            message: 'Hi',
            type: MessageLogType.Input,
        } as AssistantLogFragmentFragment;
        const { rerender, result } = renderHook(({ logs }) => usePendingInputs('repeat-flow', '42', logs), {
            initialProps: { logs: [saved] },
        });
        act(() => {
            beginPendingInput('repeat-flow', '42', 'Hi', ['old']);
        });
        expect(result.current).toHaveLength(1);
        rerender({ logs: [saved, { ...saved, id: 'new' }] });
        expect(result.current).toHaveLength(0);
    });
});
