import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import type { AssistantLogFragmentFragment } from '@/graphql/types';

import { TooltipProvider } from '@/components/ui/tooltip';
import { MessageLogType, ResultFormat } from '@/graphql/types';

import FlowMessage from './flow-message';

vi.mock('@/components/shared/markdown', () => ({
    default: ({ children }: { children: string }) => <div>{children}</div>,
}));
vi.mock('@/components/shared/terminal', () => ({ default: () => null }));

const log: AssistantLogFragmentFragment = {
    appendPart: true,
    assistantId: '1',
    createdAt: '2026-10-12T12:00:00Z',
    flowId: '1',
    id: '1',
    message: '',
    result: '',
    resultFormat: ResultFormat.Plain,
    thinking: 'Checking the calculation',
    type: MessageLogType.Answer,
};

describe('inline thinking', () => {
    it('remains visible as thinking grows, answer text arrives, and search clears', () => {
        const view = (value: AssistantLogFragmentFragment, searchValue = '') => (
            <TooltipProvider>
                <FlowMessage
                    log={value}
                    searchValue={searchValue}
                />
            </TooltipProvider>
        );
        const { rerender } = render(view(log));
        expect(screen.getByText('Checking the calculation')).toBeVisible();
        const completed = { ...log, appendPart: false, message: '323', thinking: 'Checked multiplication' };
        rerender(view(completed));
        expect(screen.getByText('Checked multiplication')).toBeVisible();
        expect(screen.getByText('323')).toBeVisible();
        rerender(view(completed, '323'));
        rerender(view(completed));
        expect(screen.getByText('Checked multiplication')).toBeVisible();
        fireEvent.click(screen.getByRole('button', { name: 'Hide thinking' }));
        expect(screen.queryByText('Checked multiplication')).not.toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: 'Show thinking' }));
        expect(screen.getByText('Checked multiplication')).toBeVisible();
    });
});
