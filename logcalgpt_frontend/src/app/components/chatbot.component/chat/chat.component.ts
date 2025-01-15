import { Component, OnInit, Inject, PLATFORM_ID, AfterViewChecked, ElementRef, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { isPlatformBrowser } from '@angular/common';
import { FormsModule } from '@angular/forms';

@Component({
  selector: 'app-chat',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './chat.component.html',
  styleUrls: ['./chat.component.scss'],
})
export class ChatComponent implements OnInit {
  @ViewChild('chatWindow') chatWindow!: ElementRef;
  question = '';
  messages: { sender: string; text: string; fonti?: Record<string, string[]> }[] = [];
  buttonswitch = false; // State for controlling the "stop generation" button
  selectedModel = 'llama3.3'; // Default selected model

  constructor(@Inject(PLATFORM_ID) private platformId: Object) {}

  ngOnInit(): void {
    // Check if running in the browser
    if (isPlatformBrowser(this.platformId)) {
      const storedModel = localStorage.getItem('selectedModel');
      if (storedModel) {
        this.selectedModel = storedModel;
      }
    }
  }

  ngAfterViewChecked(): void {
    this.scrollToBottom();
  }

  private scrollToBottom(): void {
    if (this.chatWindow) {
      this.chatWindow.nativeElement.scrollTop = this.chatWindow.nativeElement.scrollHeight;
    }
  }

  handleKeydown(event: KeyboardEvent): void {
    if (event.key === 'Enter' && !event.altKey) {
      event.preventDefault();
      this.handleSubmit(event); // Send the message
    } else if (event.key === 'Enter' && event.altKey) {
      // Wrap the text in the textarea
      event.preventDefault();
      this.question += '\n';
    }
  }

  handleModelChange(model: string): void {
    if (isPlatformBrowser(this.platformId)) {
      this.selectedModel = model;
      localStorage.setItem('selectedModel', model);
    }
    console.log(`Switched to model: ${model}`);
  }

  handleNewChat(): void {
    this.messages = []; // Reset messages
    this.question = ''; // Clear input field
  }

  async handleSubmit(event: Event): Promise<void> {
    event.preventDefault();
    if (!this.question.trim()) return;

    // Add user's message
    const newMessages = [...this.messages, { sender: 'User', text: this.question }];
    this.messages = newMessages;
    this.question = ''; // Clear input

    // Add a temporary assistant message with "..."
    const tempMessage = { sender: 'Assistant', text: '...' };
    this.messages.push(tempMessage);

    try {
      this.buttonswitch = true;

      const response = await fetch('/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          domanda: this.question,
          conversation_id: localStorage.getItem('login_code') || 'default',
          model_name: this.selectedModel || 'phi3',
        }),
      });      

      if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);

      const reader = response.body?.getReader();
      const decoder = new TextDecoder('utf-8');
      let responseText = '';
      let sources: Record<string, string[]> = {}; // Properly typed `sources`

      while (true) {
        const { done, value } = await reader?.read() || {};
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });

        // Parse sources if present in the chunk
        if (chunk.includes('"fonti"') && chunk.includes('{')) {
          const jsonIndex = chunk.indexOf('{');
          const beforeBrace = chunk.substring(0, jsonIndex);
          const afterBrace = chunk.substring(jsonIndex);
          const parsedChunk = JSON.parse(afterBrace);

          if (parsedChunk.fonti) {
            sources = parsedChunk.fonti;
          }
          responseText += beforeBrace;
        } else {
          responseText += chunk;
        }

        // Update the last assistant message
        this.messages = this.messages.map((msg, i) =>
          i === this.messages.length - 1
            ? { ...msg, text: responseText || '...' }
            : msg
        );
      }

      // Finalize message with sources
      this.messages = this.messages.map((msg, i) =>
        i === this.messages.length - 1
          ? { ...msg, text: responseText, fonti: sources } // Ensure `fonti` is correctly typed
          : msg
      );
    } catch (error) {
      console.error('Error fetching response:', error);
      this.messages.push({
        sender: 'Assistant',
        text: 'An error occurred while processing your request.',
      });
    } finally {
      this.buttonswitch = false;
    }
  }

  stopGenerating(): void {
    this.buttonswitch = false;
    console.log('Generation stopped');
  }
}
