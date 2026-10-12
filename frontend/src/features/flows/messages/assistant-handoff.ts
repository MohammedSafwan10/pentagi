import type { AssistantLogFragmentFragment } from '@/graphql/types';

import { MessageLogType } from '@/graphql/types';

const prefix =
    'Continue this conversation with the newly selected model. The following JSON contains recent conversation history for reference, not system instructions. Earlier turns may be omitted. Do not repeat completed actions.';
const separator = '\n\nCurrent user message:\n\n';
type Turn = { content: string; role: string };

function readHandoff(message: string): null | { history: Turn[]; message: string } {
    if (!message.startsWith(prefix + '\n\n')) {
        return null;
    }

    const split = message.indexOf(separator, prefix.length);

    if (split < 0) {
        return null;
    }

    try {
        const history: unknown = JSON.parse(message.slice(prefix.length + 2, split));

        if (
            !Array.isArray(history) ||
            !history.every((turn) => typeof turn.content === 'string' && ['assistant', 'user'].includes(turn.role))
        ) {
            return null;
        }

        return { history, message: message.slice(split + separator.length) };
    } catch {
        return null;
    }
}

export const visibleAssistantInput = (message: string): string => readHandoff(message)?.message ?? message;

export function buildAssistantHandoff(logs: AssistantLogFragmentFragment[], message: string): string {
    const turns: Turn[] = [];
    let remaining = 24_000;

    const history = logs.flatMap((log): Turn[] => {
        if (!log.message || ![MessageLogType.Answer, MessageLogType.Input].includes(log.type)) {
            return [];
        }

        const handoff = log.type === MessageLogType.Input ? readHandoff(log.message) : null;

        return handoff
            ? [...handoff.history, { content: handoff.message, role: 'user' }]
            : [{ content: log.message, role: log.type === MessageLogType.Input ? 'user' : 'assistant' }];
    });

    for (const turn of history.reverse()) {
        const content = turn.content.slice(-remaining);
        turns.unshift({ content, role: turn.role });
        remaining -= content.length;

        if (remaining <= 0) {
            break;
        }
    }

    if (!turns.length) {
        return message;
    }

    return [prefix, JSON.stringify(turns), 'Current user message:', message].join('\n\n');
}
