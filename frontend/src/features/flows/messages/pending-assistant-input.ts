import { useEffect, useMemo, useSyncExternalStore } from 'react';

import type { AssistantLogFragmentFragment } from '@/graphql/types';

import { MessageLogType, ResultFormat } from '@/graphql/types';

interface PendingInput {
    assistantId: null | string;
    flowId: string;
    knownIds: string[];
    log: AssistantLogFragmentFragment;
}

let inputs: PendingInput[] = [];
const listeners = new Set<() => void>();

const subscribe = (listener: () => void) => {
    listeners.add(listener);

    return () => {
        listeners.delete(listener);
    };
};

const snapshot = () => inputs;

const publish = (next: PendingInput[]) => {
    inputs = next;
    listeners.forEach((listener) => listener());
};

export function assignPendingInput(id: string, flowId: string, assistantId: string): void {
    publish(
        inputs.map((input) =>
            input.log.id === id ? { ...input, assistantId, flowId, log: { ...input.log, assistantId, flowId } } : input,
        ),
    );
}

export function beginPendingInput(
    flowId: string,
    assistantId: null | string,
    message: string,
    knownIds: string[] = [],
): string {
    const id = 'pending-' + crypto.randomUUID();
    publish([
        ...inputs,
        {
            assistantId,
            flowId,
            knownIds,
            log: {
                appendPart: false,
                assistantId: assistantId ?? '',
                createdAt: new Date().toISOString(),
                flowId,
                id,
                message,
                result: '',
                resultFormat: ResultFormat.Plain,
                thinking: null,
                type: MessageLogType.Input,
            },
        },
    ]);

    return id;
}

export function removePendingInput(id: string): void {
    publish(inputs.filter((input) => input.log.id !== id));
}

const isSaved = (input: PendingInput, logs: AssistantLogFragmentFragment[]) =>
    logs.some(
        (log) =>
            log.assistantId === input.assistantId &&
            log.type === MessageLogType.Input &&
            log.message === input.log.message &&
            !input.knownIds.includes(log.id),
    );

export function usePendingInputs(
    flowId: null | string,
    assistantId: null | string,
    logs: AssistantLogFragmentFragment[],
) {
    const pending = useSyncExternalStore(subscribe, snapshot, snapshot);
    useEffect(() => {
        const saved = pending.filter((input) => input.flowId === flowId && isSaved(input, logs));

        if (saved.length) {
            const ids = new Set(saved.map((input) => input.log.id));
            publish(inputs.filter((input) => !ids.has(input.log.id)));
        }
    }, [flowId, logs, pending]);

    return useMemo(
        () =>
            pending
                .filter(
                    (input) =>
                        input.flowId === flowId &&
                        (input.assistantId === null || input.assistantId === assistantId) &&
                        !isSaved(input, logs),
                )
                .map((input) => input.log),
        [assistantId, flowId, logs, pending],
    );
}
