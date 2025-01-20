// src/app/services/chat.service.ts

import { Injectable } from '@angular/core';
import { Observable, Subject } from 'rxjs';

@Injectable({
  providedIn: 'root',
})
export class ChatService {
  private apiUrl = 'http://127.0.0.1:8000/api'; // Update if different
  private conversationId: string = 'default'; // You can generate unique IDs as needed

  constructor() {}

  /**
   * Initializes a new conversation by calling the /new_ask/ endpoint.
   * @param conversationId Unique identifier for the conversation
   */
  initializeConversation(conversationId: string = 'default'): Observable<any> {
    const url = `${this.apiUrl}/new_ask/`;
    const body = { conversation_id: conversationId };

    return new Observable((observer) => {
      fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(body),
      })
        .then((response) => response.json())
        .then((data) => {
          if (data.valid) {
            this.conversationId = conversationId;
            observer.next(data);
            observer.complete();
          } else {
            observer.error('Failed to initialize conversation.');
          }
        })
        .catch((error) => {
          observer.error(error);
        });
    });
  }

  /**
   * Sends a user message to the /ask/ endpoint and streams the response.
   * @param message The user's message
   * @param modelName The selected model name
   */
  sendMessage(message: string, modelName: string): Observable<string> {
    const url = `${this.apiUrl}/ask/`;
    const body = {
      domanda: message,
      conversation_id: this.conversationId,
      model_name: modelName, // Use the dynamic model name
    };

    const subject = new Subject<string>();

    fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    })
      .then((response) => {
        if (!response.body) {
          throw new Error('ReadableStream not supported in this browser.');
        }
        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');

        const read = () => {
          reader.read().then(({ done, value }) => {
            if (done) {
              subject.complete();
              return;
            }
            const chunk = decoder.decode(value, { stream: true });
            subject.next(chunk);
            read();
          });
        };

        read();
      })
      .catch((error) => {
        subject.error(error);
      });

    return subject.asObservable();
  }

  /**
   * Generates a unique conversation ID.
   * You can enhance this method to generate UUIDs or other unique identifiers.
   */
  generateConversationId(): string {
    return 'convo_' + Math.random().toString(36).substring(2, 15);
  }
}
