import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import Markdown from './markdown';

const tableMarkdown = [
    '| Name | Email | Token |',
    '| --- | --- | --- |',
    '| sample | sample@example.com | TOKEN{0000000000000000000000000000000000000000000000000000000000000000} |',
].join('\n');

afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
});

describe('Markdown', () => {
    it('copies only the selected block, retaining indentation and newlines with highlighting enabled', async () => {
        const writeText = vi.fn().mockResolvedValue(undefined);
        vi.stubGlobal('navigator', { clipboard: { writeText } });
        render(
            <Markdown searchValue="echo">
                {'Outside\n\n```bash\necho "hello"\n  echo "world"\n```\n\n```\nother block\n```'}
            </Markdown>,
        );
        fireEvent.click(screen.getAllByRole('button', { name: 'Copy code block' })[0]!);
        await waitFor(() => expect(screen.getByText('Copied')).toBeInTheDocument());
        expect(writeText).toHaveBeenCalledWith('echo "hello"\n  echo "world"\n');
        expect(screen.getAllByRole('button', { name: 'Copy code block' })[1]).toHaveTextContent('Copy');
    });

    it('allows retry after clipboard access fails and leaves inline code without a button', async () => {
        const writeText = vi.fn().mockRejectedValueOnce(new Error('Denied')).mockResolvedValue(undefined);
        vi.stubGlobal('navigator', { clipboard: { writeText } });
        render(<Markdown>{'Inline `text`\n\n```\ncommand\n```'}</Markdown>);
        const button = screen.getByRole('button', { name: 'Copy code block' });
        fireEvent.click(button);
        await waitFor(() => expect(button).toHaveTextContent('Copy failed—retry'));
        fireEvent.click(button);
        await waitFor(() => expect(button).toHaveTextContent('Copied'));
        expect(writeText).toHaveBeenLastCalledWith('command\n');
    });

    it('wraps a table in a horizontally scrollable container so wide content cannot widen the message list', () => {
        const { container } = render(<Markdown>{tableMarkdown}</Markdown>);

        const table = container.querySelector('table');
        expect(table).not.toBeNull();
        expect(table?.parentElement?.className).toContain('overflow-x-auto');
    });

    it('keeps the table wrapped when search highlighting is active', () => {
        const { container } = render(<Markdown searchValue="sample">{tableMarkdown}</Markdown>);

        const table = container.querySelector('table');
        expect(table?.parentElement?.className).toContain('overflow-x-auto');
    });

    it('takes a named tab stop while the table is wider than the space it has', () => {
        vi.spyOn(Element.prototype, 'scrollWidth', 'get').mockReturnValue(743);
        vi.spyOn(Element.prototype, 'clientWidth', 'get').mockReturnValue(606);

        const { container } = render(<Markdown>{tableMarkdown}</Markdown>);

        const region = container.querySelector('table')?.parentElement;
        expect(region).toHaveAttribute('tabindex', '0');
        expect(region).toHaveAttribute('role', 'region');
        expect(region).toHaveAccessibleName('Table');
    });

    it('stays out of the tab order when the whole table fits', () => {
        vi.spyOn(Element.prototype, 'scrollWidth', 'get').mockReturnValue(606);
        vi.spyOn(Element.prototype, 'clientWidth', 'get').mockReturnValue(606);

        const { container } = render(<Markdown>{tableMarkdown}</Markdown>);

        expect(container.querySelector('table')?.parentElement).not.toHaveAttribute('tabindex');
    });
});
