import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { TooltipProvider } from '@/components/ui/tooltip';
import { StatusType } from '@/graphql/types';

import type { FlowFormValues } from '../flow-form';

const { flowState, formProps, providersState } = vi.hoisted(() => ({
    flowState: { current: {} as Record<string, unknown> },
    formProps: [] as {
        defaultValues?: { providerName?: string };
        onSubmit?: (values: FlowFormValues) => Promise<boolean>;
    }[],
    providersState: { current: {} as Record<string, unknown> },
}));

vi.mock('@/hooks/use-auto-scroll', () => ({
    useAutoScroll: () => ({
        containerRef: () => {},
        endRef: { current: null },
        hasNewMessages: false,
        isScrolledToBottom: false,
        scrollToEnd: vi.fn(),
    }),
}));

vi.mock('@/providers/flow-provider', () => ({ useFlow: () => flowState.current }));
vi.mock('@/providers/providers-provider', () => ({ useProviders: () => providersState.current }));
vi.mock('@/providers/system-settings-provider', () => ({ useSystemSettings: () => ({ settings: null }) }));

vi.mock('../flow-form', () => ({
    FlowForm: (props: {
        defaultValues?: { providerName?: string };
        onSubmit?: (values: FlowFormValues) => Promise<boolean>;
    }) => {
        formProps.push(props);

        return <div />;
    },
}));
vi.mock('./flow-message', () => ({ default: () => <div /> }));

const { default: FlowAssistantMessages } = await import('./flow-assistant-messages');

const renderComposer = (state: Record<string, unknown>) => {
    formProps.length = 0;
    providersState.current = {
        providers: [{ name: 'anthropic', type: 'anthropic' }],
        selectedProvider: { name: 'anthropic', type: 'anthropic' },
    };
    flowState.current = {
        assistantLogs: [],
        assistants: [],
        createAssistant: vi.fn(),
        deleteAssistant: vi.fn(),
        flowId: '42',
        flowStatus: StatusType.Running,
        initiateAssistantCreation: vi.fn(),
        selectAssistant: vi.fn(),
        selectedAssistantId: null,
        stopAssistant: vi.fn(),
        submitAssistantMessage: vi.fn(),
        ...state,
    };

    render(
        <MemoryRouter>
            <TooltipProvider>
                <FlowAssistantMessages />
            </TooltipProvider>
        </MemoryRouter>,
    );

    return formProps.at(-1)?.defaultValues?.providerName;
};

describe('the assistant composer defaults its provider the way /flows/new does', () => {
    it('falls back to the remembered provider when no assistant is selected yet', () => {
        expect(renderComposer({})).toBe('anthropic');
    });

    it('keeps the selected assistant own provider rather than the remembered one', () => {
        const providerName = renderComposer({
            assistants: [
                { id: '5', provider: { name: 'openai' }, status: StatusType.Running, title: 'Recon assistant' },
            ],
            selectedAssistantId: '5',
        });

        expect(providerName).toBe('openai');
    });
});

afterEach(cleanup);

describe('assistant startup and recovery', () => {
    it.each(['custom', 'GLM 5.3 Flash'])(
        'continues the same assistant when agents or provider changes (%s)',
        async (providerName) => {
            const createAssistant = vi.fn();
            const submitAssistantMessage = vi.fn().mockResolvedValue(true);
            renderComposer({
                assistants: [{ id: '5', provider: { name: 'custom' }, status: StatusType.Waiting, title: 'Chat' }],
                createAssistant,
                selectedAssistantId: '5',
                submitAssistantMessage,
            });
            const values = { message: 'Hello', providerName, resourceIds: [], useAgents: true };
            await formProps.at(-1)?.onSubmit?.(values);
            expect(submitAssistantMessage).toHaveBeenCalledWith('5', values);
            expect(createAssistant).not.toHaveBeenCalled();
        },
    );
    it('allows a replacement assistant after a selected assistant fails', () => {
        const initiateAssistantCreation = vi.fn();
        renderComposer({
            assistants: [{ id: '5', provider: { name: 'anthropic' }, status: StatusType.Failed, title: 'Failed' }],
            initiateAssistantCreation,
            selectedAssistantId: '5',
        });
        fireEvent.click(screen.getByRole('button', { name: 'Create new assistant' }));
        expect(initiateAssistantCreation).toHaveBeenCalledOnce();
    });

    it('offers a new flow when setup failed rather than suggesting an assistant on the broken flow', () => {
        renderComposer({ flowStatus: StatusType.Failed });
        expect(screen.getByRole('link', { name: 'Create new flow' })).toHaveAttribute('href', '/flows/new');
        expect(screen.queryByRole('button', { name: 'Create new assistant' })).not.toBeInTheDocument();
    });

    it('explains that the message was accepted while the first session is starting', () => {
        renderComposer({
            assistants: [{ id: '5', provider: { name: 'anthropic' }, status: StatusType.Created, title: 'Starting' }],
            selectedAssistantId: '5',
        });
        expect(screen.getByText('Preparing your assistant')).toBeInTheDocument();
        expect(screen.getByText(/Your message was accepted/)).toBeInTheDocument();
    });
});
