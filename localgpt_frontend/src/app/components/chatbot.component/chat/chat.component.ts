// chat.component.ts
import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http'; // Keep HttpClient import

interface ChatMessage {
  text: string;
  sender: 'user' | 'bot';
}

@Component({
  selector: 'app-chat',
  standalone: true,
  imports: [CommonModule, FormsModule], // Removed HttpClientModule
  templateUrl: './chat.component.html',
  styleUrls: ['./chat.component.scss'],
})
export class ChatComponent {
  constructor(private http: HttpClient) {}

  // Example conversation lists on the sidebar (optional)
  recentConversations = [];

  // These fields can be changed dynamically if you want
  conversationId = 'default';
  modelName = 'phi3';
  // initialize empty messages array
  messages: ChatMessage[] = [];
  userInput = '';

  isTyping = false;
  abortController: AbortController | null = null;

  async onSendMessage() {
    if (this.isTyping) {
      return;  // Prevent multiple requests at the same time
    }

    const question = this.userInput.trim();
    if (!question) {
      return;
    }

    // Clear the input field and add the user's message to the chat
    this.userInput = '';
    this.messages.push({ text: question, sender: 'user' });

    // Show typing indicator
    this.isTyping = true;
    this.abortController = new AbortController();
    const { signal } = this.abortController;

    const payload = {
      question: question,
      conversation_id: this.conversationId,
      model_name: this.modelName,
    };

    try {
      const response = await fetch('http://127.0.0.1:8000/api/ask/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
        signal,  // Attach the abort signal to the fetch request
      });

      if (!response.ok) {
        throw new Error(`Server error: ${response.statusText}`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder('utf-8');
      let done = false;
      let botReply = '';

      // Add an empty bot message to be updated incrementally
      this.messages.push({ text: '', sender: 'bot' });
      const botMessageIndex = this.messages.length - 1;

      while (!done && reader) {
        const { value, done: doneReading } = await reader.read();
        done = doneReading;
        if (value) {
          const chunk = decoder.decode(value, { stream: true });
          botReply += chunk;

          // Update the last bot message dynamically with streamed data
          this.messages[botMessageIndex].text = botReply;
        }
      }

    } catch (error: any) {
      if (error.name === 'AbortError') {
        this.messages.push({ text: 'Response generation stopped.', sender: 'bot' });
      } else {
        console.error('Error from /ask endpoint:', error);
        this.messages.push({ text: 'Oops! Something went wrong. Please try again.', sender: 'bot' });
      }
    } finally {
      this.isTyping = false;
      this.abortController = null;  // Reset the abort controller after completion
    }
  }

  stopGenerating() {
    if (this.abortController) {
      this.abortController.abort();  // Stop the fetch request
      this.isTyping = false;
      this.messages.push({ text: 'Response generation stopped.', sender: 'bot' });
    }
  }  
}  