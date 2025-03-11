import { Component, OnInit } from '@angular/core';
import { ChatComponent } from './components/chat/chat.component';
import { SidebarComponent } from './components/sidebar/sidebar.component';
import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';

interface DocumentHistory {
  name: string;
  result: string;
}

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [
    ChatComponent,
    SidebarComponent,
    CommonModule
  ],
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.scss']
})
export class AppComponent implements OnInit {
  // Model dropdown
  selectedModel = '';
  models: string[] = [];
  isDropdownOpen = false;

  // Sidebar document history
  recentConversations: DocumentHistory[] = [];

  constructor(private http: HttpClient) {}

  ngOnInit(): void {
    this.fetchModels();
  }

  fetchModels(): void {
    this.http.get<{ models: string[] }>('http://127.0.0.1:8080/api/get-models/')
      .subscribe(response => {
        if (response.models.length > 0) {
          this.models = response.models;
          this.selectedModel = this.models[0]; // Default to first model
        }
      }, error => {
        console.error('Error fetching models:', error);
      });
  }

  // Dropdown toggle
  toggleDropdown(): void {
    this.isDropdownOpen = !this.isDropdownOpen;
  }

  // User selects a model
  selectModel(model: string): void {
    this.selectedModel = model;
    this.isDropdownOpen = false;
    console.log('Selected model:', this.selectedModel);
  }

  // Called when sidebar wants a "new document"
  onNewDocument(): void {
    // For example, clear the current chat or start a new conversation
    console.log('Start a new conversation');
  }

  // Called when user selects a document from the history
  loadDocument(document: DocumentHistory): void {
    // If you want to load a conversation in <app-chat> or do something with it
    console.log('Loading document:', document.name);
  }

  // Clear conversation history
  onClearHistory(): void {
    this.recentConversations = [];
    // localStorage.removeItem('documentHistory');
    console.log('Cleared conversation history');
  }
}
