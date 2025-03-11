import { Component, EventEmitter, Input, Output, ViewChild, ElementRef, AfterViewInit } from '@angular/core';
import { CommonModule } from '@angular/common';

interface DocumentHistory {
  name: string;
  result: string;
}

@Component({
  selector: 'app-sidebar',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './sidebar.component.html',
  styleUrls: ['./sidebar.component.scss'],
})
export class SidebarComponent implements AfterViewInit {
  @Input() recentConversations: DocumentHistory[] = [];
  @Output() newDocument = new EventEmitter<void>();
  @Output() documentSelected = new EventEmitter<DocumentHistory>();
  @Output() clearHistory = new EventEmitter<void>();  // New Output event for clearing history

  @ViewChild('conversationList') conversationList!: ElementRef<HTMLDivElement>;

  ngAfterViewInit(): void {
    this.scrollToBottom();
  }

  ngOnChanges(): void {
    this.scrollToBottom();
  }

  triggerNewDocument() {
    this.newDocument.emit();
  }

  loadDocument(doc: DocumentHistory) {
    this.documentSelected.emit(doc);
  }

  clearHistoryTrigger() {
    this.clearHistory.emit();  // Notify parent to clear history permanently
  }

  private scrollToBottom() {
    if (this.conversationList) {
      setTimeout(() => {
        this.conversationList.nativeElement.scrollTop = this.conversationList.nativeElement.scrollHeight;
      }, 100);
    }
  }
}
