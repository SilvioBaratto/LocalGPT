import { Component, Input, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { MarkdownPipe } from '../../pipes/markdown.pipe';

interface ChatMessage {
  text: string;
  sender: 'user' | 'bot';
  sources?: any;
  showSources?: boolean;
}

@Component({
  selector: 'app-chat',
  standalone: true,
  imports: [CommonModule, FormsModule, MarkdownPipe],
  templateUrl: './chat.component.html',
  styleUrls: ['./chat.component.scss'],
})
export class ChatComponent implements OnInit {
  @Input() modelName: string = '';
  messages: ChatMessage[] = [];
  userInput = '';
  isTyping = false;
  abortController: AbortController | null = null;
  conversationId: string = '';

  constructor(private http: HttpClient) {}

  ngOnInit(): void {
    this.conversationId = crypto.randomUUID();
  }

  async onSendMessage() {
    if (this.isTyping) {
      return;
    }

    const question = this.userInput.trim();
    if (!question) {
      return;
    }

    this.userInput = '';
    this.messages.push({ text: question, sender: 'user' });

    this.isTyping = true;
    this.abortController = new AbortController();
    const { signal } = this.abortController;

    const payload = {
      question: question,
      conversation_id: this.conversationId,
      model_name: this.modelName,
    };

    try {
      const response = await fetch('http://127.0.0.1:8080/api/chat/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        signal,
      });

      if (!response.ok) {
        throw new Error(`Server error: ${response.statusText}`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder('utf-8');
      let done = false;
      let botReply = '';

      // Push an empty bot message to update as the stream comes in.
      this.messages.push({ text: '', sender: 'bot' });
      const botMessageIndex = this.messages.length - 1;

      while (!done && reader) {
        const { value, done: doneReading } = await reader.read();
        done = doneReading;
        if (value) {
          const chunk = decoder.decode(value, { stream: true });
          botReply += chunk;
          this.messages[botMessageIndex].text = botReply;
        }
      }

      // After complete, check if the response contains an appended JSON block
      const jsonStartIndex = botReply.lastIndexOf('{"response":');
      if (jsonStartIndex !== -1) {
        const answerText = botReply.substring(0, jsonStartIndex).trim();
        const jsonPart = botReply.substring(jsonStartIndex).trim();
        try {
          const parsed = JSON.parse(jsonPart);
          this.messages[botMessageIndex].text = answerText;
          this.messages[botMessageIndex].sources = parsed.sources;
          this.messages[botMessageIndex].showSources = false;
        } catch (e) {
          console.error('Error parsing sources JSON:', e);
        }
      }
    } catch (error: any) {
      if (error.name === 'AbortError') {
        this.messages.push({
          text: 'Response generation stopped.',
          sender: 'bot',
        });
      } else {
        console.error('Error from /chat endpoint:', error);
        this.messages.push({
          text: 'Oops! Something went wrong. Please try again.',
          sender: 'bot',
        });
      }
    } finally {
      this.isTyping = false;
      this.abortController = null;
    }
  }

  stopGenerating() {
    if (this.abortController) {
      this.abortController.abort();
      this.isTyping = false;
      this.messages.push({
        text: 'Response generation stopped.',
        sender: 'bot',
      });
    }
  }

  toggleSources(msg: ChatMessage): void {
    msg.showSources = !msg.showSources;
  }

  getSourceKeys(sources: any): string[] {
    return Object.keys(sources);
  }
}
