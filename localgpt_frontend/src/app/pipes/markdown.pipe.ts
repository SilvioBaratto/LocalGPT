import { Pipe, PipeTransform } from '@angular/core';
import { marked, Renderer, Tokens, Parser } from 'marked';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import DOMPurify from 'dompurify';

@Pipe({
  name: 'markdown',
  standalone: true,
  pure: true,
})
export class MarkdownPipe implements PipeTransform {
  private renderer: Renderer;
  private parser: Parser;
  private lastValue: string | null = null;
  private lastResult: SafeHtml | null = null;

  constructor(private sanitizer: DomSanitizer) {
    this.renderer = new Renderer();
    this.parser = new Parser();

    // --- Customized Rendering Functions ---

    // Headings
    this.renderer.heading = (token: Tokens.Heading): string => {
      const text = this.parser.parseInline(token.tokens);
      const depth = token.depth;
      // Remove color and just keep size/spacing
      const classes =
        depth === 1
          ? 'text-3xl font-bold mb-6'
          : depth === 2
          ? 'text-2xl font-semibold mb-4'
          : depth === 3
          ? 'text-xl font-medium mb-3'
          : 'text-lg font-medium mb-2';
    
      return `<h${depth} class="${classes}">${text}</h${depth}>`;
    };

    // Paragraphs
    this.renderer.paragraph = (token: Tokens.Paragraph): string => {
      const text = this.parser.parseInline(token.tokens);
      // Remove the color; keep text size consistent (e.g. 'text-base' or 'text-lg')
      return `<p class="mb-4 text-base leading-relaxed">${text}</p>`;
    };

    // Horizontal Rule
    this.renderer.hr = (_token: Tokens.Hr): string => {
      return `<hr class="my-8 border-t-2 border-[#2F6DD5]" />`;
    };

    // Blockquote
    this.renderer.blockquote = (token: Tokens.Blockquote): string => {
      const content = this.parser.parse(token.tokens);
      return `
        <blockquote class="border-l-4 border-blue-500 pl-5 italic text-gray-700 bg-blue-50 rounded-md py-2 mb-6 shadow-sm">
          ${content}
        </blockquote>
      `;
    };

    // Tables
    this.renderer.table = (token: Tokens.Table): string => {
      const headerHtml = token.header
        .map((cellTokens) => {
          const content = this.parser.parseInline(cellTokens.tokens);
          return `<th class="px-6 py-3 bg-blue-100 text-left text-sm font-semibold text-blue-700 uppercase">${content}</th>`;
        })
        .join('');

      const bodyHtml = token.rows
        .map((row) => {
          const rowCells = row
            .map((cellTokens) => {
              const content = this.parser.parseInline(cellTokens.tokens);
              return `<td class="px-6 py-4 text-sm text-gray-700">${content}</td>`;
            })
            .join('');
          return `<tr class="even:bg-blue-50 hover:bg-blue-100">${rowCells}</tr>`;
        })
        .join('');

      return `
        <div class="overflow-x-auto">
          <table class="min-w-full border border-gray-300 divide-y divide-gray-200 rounded-lg shadow">
            <thead>${headerHtml}</thead>
            <tbody>${bodyHtml}</tbody>
          </table>
        </div>
      `;
    };

    // Register the renderer with marked.
    marked.use({ renderer: this.renderer });
  }

  transform(value: string | null): SafeHtml {
    if (!value) {
      return '';
    }

    if (value === this.lastValue && this.lastResult) {
      return this.lastResult;
    }

    const html = marked.parse(value);
    const sanitizedHtml = DOMPurify.sanitize(html as string);
    const safeHtml = this.sanitizer.bypassSecurityTrustHtml(sanitizedHtml);

    this.lastValue = value;
    this.lastResult = safeHtml;

    return safeHtml;
  }
}
