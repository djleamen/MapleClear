/**
 * MapleClear Content Script
 * 
 * Injects the simplification panel and handles text selection/extraction
 * for Canadian government webpages.
 */

declare const browser: any;

interface Config {
  API_BASE: string;
  PANEL_ID: string;
  TRIGGER_DOMAINS: string[];
}

interface SelectionInfo {
  text: string;
  range?: Range;
  element?: Element;
}

const CONFIG: Config = {
  API_BASE: 'http://127.0.0.1:11434',
  PANEL_ID: 'mapleclear-panel',
  TRIGGER_DOMAINS: ['canada.ca', 'gc.ca']
};

class MapleClearContentScript {
  private panel: HTMLElement | null = null;
  private currentSelection: SelectionInfo | null = null;

  public async init(): Promise<void> {
    if (!this.shouldActivate()) {
      return;
    }

    this.injectStyles();

    browser.runtime.onMessage.addListener(this.handleMessage.bind(this));

    document.addEventListener('mouseup', this.handleSelection.bind(this));
    document.addEventListener('keyup', this.handleSelection.bind(this));

    this.setupAcronymDetection();

    console.log('🍁 MapleClear content script loaded');
  }

  private shouldActivate(): boolean {
    const hostname = window.location.hostname;
    const isLocalhost = hostname === 'localhost' || hostname === '127.0.0.1';
    const isGovernment = CONFIG.TRIGGER_DOMAINS.some(domain => 
      hostname.includes(domain)
    );
    
    return isLocalhost || isGovernment;
  }

  private injectStyles(): void {
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = browser.runtime.getURL('content-styles.css');
    document.head.appendChild(link);
  }

  private async handleMessage(message: any): Promise<any> {
    switch (message.type) {
      case 'TOGGLE_PANEL':
        return this.togglePanel();
      
      case 'SIMPLIFY_SELECTION':
        return this.simplifySelection();
      
      case 'SIMPLIFY_PAGE':
        return this.simplifyPage();
      
      case 'TRANSLATE_TEXT':
        return this.translateText(message.targetLanguage);
      
      case 'CREATE_SPLIT_SCREEN':
        return this.createSplitScreen(message.action, message.language, message.languageName);
      
      case 'GET_PAGE_INFO':
        return this.getPageInfo();
      
      default:
        return { success: false, error: 'Unknown message type' };
    }
  }

  private async togglePanel(): Promise<{ success: boolean }> {
    if (this.panel) {
      this.removePanel();
    } else {
      await this.createPanel();
    }
    return { success: true };
  }

  private async createPanel(): Promise<void> {
    this.removePanel();

    this.panel = document.createElement('div');
    this.panel.id = CONFIG.PANEL_ID;
    this.panel.className = 'mapleclear-panel';
    
    const panelURL = browser.runtime.getURL('panel.html');
    try {
      const response = await fetch(panelURL);
      const html = await response.text();
      this.panel.innerHTML = html;
    } catch (error) {
      console.error('Failed to load panel HTML:', error);
      this.panel.innerHTML = '<div class="error">Failed to load MapleClear panel</div>';
    }

    document.body.appendChild(this.panel);

    this.setupPanelEvents();
  }

  private removePanel(): void {
    if (this.panel) {
      this.panel.remove();
      this.panel = null;
    }
  }

  private setupPanelEvents(): void {
    if (!this.panel) return;

    const closeBtn = this.panel.querySelector('.close-button');
    closeBtn?.addEventListener('click', () => this.removePanel());

    const simplifySelectionBtn = this.panel.querySelector('#simplify-selection');
    simplifySelectionBtn?.addEventListener('click', () => this.simplifySelection());

    const simplifyPageBtn = this.panel.querySelector('#simplify-page');
    simplifyPageBtn?.addEventListener('click', () => this.simplifyPage());

    const translateBtn = this.panel.querySelector('#translate');
    translateBtn?.addEventListener('click', () => this.translateText('fr'));
  }

  private handleSelection(): void {
    const selection = window.getSelection();
    if (!selection || selection.isCollapsed) {
      this.currentSelection = null;
      return;
    }

    const text = selection.toString().trim();
    if (text.length < 10) {
      this.currentSelection = null;
      return;
    }

    this.currentSelection = {
      text,
      range: selection.getRangeAt(0).cloneRange()
    };

    if (this.panel) {
      this.updateSelectionInfo();
    }
  }

  private updateSelectionInfo(): void {
    if (!this.panel) return;

    const info = this.panel.querySelector('.selection-info');
    if (info) {
      if (this.currentSelection) {
        info.textContent = `Selected: ${this.currentSelection.text.substring(0, 50)}...`;
        info.classList.remove('hidden');
      } else {
        info.classList.add('hidden');
      }
    }
  }

  private async simplifySelection(): Promise<{ success: boolean; data?: any; error?: string }> {
    if (!this.currentSelection) {
      return { success: false, error: 'No text selected' };
    }

    return this.processText('simplify', this.currentSelection.text);
  }

  private async simplifyPage(): Promise<{ success: boolean; data?: any; error?: string }> {
    const mainContent = this.extractMainContent();
    return this.processText('simplify', mainContent);
  }

  private async translateText(targetLanguage: string): Promise<{ success: boolean; data?: any; error?: string }> {
    const text = this.currentSelection?.text || this.extractMainContent();
    return this.processText('translate', text, { targetLanguage });
  }

  private extractMainContent(): string {
    const selectors = [
      'main',
      '[role="main"]',
      '.main-content',
      '#main-content',
      '.content',
      '#content',
      'article',
      '.article-content'
    ];

    for (const selector of selectors) {
      const element = document.querySelector(selector);
      if (element) {
        return this.extractTextFromElement(element);
      }
    }

    const body = document.body.cloneNode(true) as HTMLElement;
    
    const removeSelectors = [
      'nav', 'header', 'footer', '.nav', '.navigation', '.header', '.footer',
      '.sidebar', '.menu', '.breadcrumb', '.skip-link', '.sr-only'
    ];
    
    removeSelectors.forEach(sel => {
      body.querySelectorAll(sel).forEach(el => el.remove());
    });

    return this.extractTextFromElement(body);
  }

  private extractTextFromElement(element: Element): string {
    // Simple text extraction - could be improved to preserve formatting
    return element.textContent?.trim() || '';
  }

  private async processText(
    action: 'simplify' | 'translate', 
    text: string, 
    options: any = {}
  ): Promise<{ success: boolean; data?: any; error?: string }> {
    if (!text.trim()) {
      return { success: false, error: 'No text to process' };
    }

    this.showLoading(action);

    try {
      let endpoint: string;
      let body: any;

      if (action === 'simplify') {
        endpoint = `${CONFIG.API_BASE}/simplify`;
        body = {
          text,
          target_grade: 7,
          preserve_acronyms: true,
          context: window.location.hostname
        };
      } else if (action === 'translate') {
        endpoint = `${CONFIG.API_BASE}/translate`;
        body = {
          text,
          target_language: options.targetLanguage || 'fr',
          preserve_terms: true,
          experimental: false
        };
      } else {
        throw new Error(`Unknown action: ${action}`);
      }

      const response = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(body)
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      this.showResult(action, data);
      
      return { success: true, data };

    } catch (error) {
      console.error(`MapleClear ${action} error:`, error);
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      this.showError(errorMessage);
      return { success: false, error: errorMessage };
    }
  }

  private showLoading(action: string): void {
    if (!this.panel) return;
    
    const content = this.panel.querySelector('.panel-content');
    if (content) {
      content.innerHTML = `
        <div class="loading">
          <div class="spinner"></div>
          <p>Processing text with ${action}...</p>
        </div>
      `;
    }
  }

  private showResult(action: string, data: any): void {
    if (!this.panel) return;

    const content = this.panel.querySelector('.panel-content');
    if (!content) return;

    if (action === 'simplify') {
      content.innerHTML = `
        <div class="result">
          <h3>Simplified Text</h3>
          <div class="simplified-text">${data.plain}</div>
          
          <h4>Changes Made</h4>
          <ul class="rationale">
            ${data.rationale.map((r: string) => `<li>${r}</li>`).join('')}
          </ul>
          
          <div class="reading-grade">
            Reading level: Grade ${data.readability_grade.toFixed(1)} 
            (was ${data.original_grade.toFixed(1)})
          </div>
          
          ${data.cautions.length > 0 ? `
            <div class="cautions">
              <h4>⚠️ Please note:</h4>
              <ul>
                ${data.cautions.map((c: string) => `<li>${c}</li>`).join('')}
              </ul>
            </div>
          ` : ''}
        </div>
      `;
    } else if (action === 'translate') {
      content.innerHTML = `
        <div class="result">
          <h3>Translation (${data.target_language.toUpperCase()})</h3>
          <div class="translated-text">${data.translated}</div>
          
          <div class="confidence">
            Confidence: ${(data.confidence * 100).toFixed(0)}%
          </div>
          
          ${data.preserved_terms.length > 0 ? `
            <div class="preserved-terms">
              <h4>Preserved official terms:</h4>
              <ul>
                ${data.preserved_terms.map((t: string) => `<li>${t}</li>`).join('')}
              </ul>
            </div>
          ` : ''}
          
          ${data.cautions.length > 0 ? `
            <div class="cautions">
              <h4>⚠️ Please note:</h4>
              <ul>
                ${data.cautions.map((c: string) => `<li>${c}</li>`).join('')}
              </ul>
            </div>
          ` : ''}
        </div>
      `;
    }
  }

  private showError(message: string): void {
    if (!this.panel) return;
    
    const content = this.panel.querySelector('.panel-content');
    if (content) {
      content.innerHTML = `
        <div class="error">
          <h3>❌ Error</h3>
          <p>${message}</p>
          <p class="help-text">
            Make sure the MapleClear server is running on localhost:11434
          </p>
        </div>
      `;
    }
  }

  private setupAcronymDetection(): void {
    const acronymRegex = /\b[A-Z]{2,}\b/g;
    
    const textNodes = this.getTextNodes(document.body);
    
    textNodes.forEach(node => {
      const text = node.textContent || '';
      const matches = Array.from(text.matchAll(acronymRegex));
      
      if (matches.length > 0) {
        let newHTML = text;
        
        const sortedMatches = [...matches].reverse();
        sortedMatches.forEach((match: RegExpExecArray) => {
          const acronym = match[0];
          const index = match.index ?? 0;
          
          const before = newHTML.substring(0, index);
          const after = newHTML.substring(index + acronym.length);
          
          newHTML = before + `<span class="mapleclear-acronym" data-acronym="${acronym}" title="Click to expand ${acronym}">${acronym}</span>` + after;
        });
        
        if (node.parentElement && newHTML !== text) {
          const wrapper = document.createElement('span');
          wrapper.innerHTML = newHTML;
          node.parentElement.replaceChild(wrapper, node);
        }
      }
    });
    
    document.addEventListener('mouseenter', this.handleAcronymHover.bind(this), true);
    document.addEventListener('mouseleave', this.handleAcronymLeave.bind(this), true);
    document.addEventListener('click', this.handleAcronymClick.bind(this), true);
  }

  private async handleAcronymHover(event: Event): Promise<void> {
    const target = event.target as HTMLElement;
    if (target?.classList.contains('mapleclear-acronym')) {
      const acronym = target.dataset.acronym;
      if (acronym) {
        await this.showAcronymTooltip(target, acronym);
      }
    }
  }

  private handleAcronymLeave(event: Event): void {
    const target = event.target as HTMLElement;
    if (target?.classList.contains('mapleclear-acronym')) {
      this.hideAcronymTooltip();
    }
  }

  private async handleAcronymClick(event: Event): Promise<void> {
    const target = event.target as HTMLElement;
    if (target?.classList.contains('mapleclear-acronym')) {
      event.preventDefault();
      const acronym = target.dataset.acronym;
      if (acronym) {
        await this.expandAcronym(acronym);
      }
    }
  }

  private async showAcronymTooltip(element: HTMLElement, acronym: string): Promise<void> {
    this.hideAcronymTooltip();
    
    try {
      const response = await fetch(`${CONFIG.API_BASE}/expand-acronyms`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: acronym })
      });
      
      if (response.ok) {
        const data = await response.json();
        const expansion = data.acronyms?.[0];
        
        if (expansion) {
          this.createTooltip(element, expansion);
        }
      }
    } catch (error) {
      console.log('Could not fetch acronym expansion:', error);
      this.createTooltip(element, {
        acronym,
        expansion: 'Expansion not available',
        definition: 'Server not available - click the MapleClear extension icon to get started'
      });
    }
  }

  private createTooltip(element: HTMLElement, expansion: any): void {
    const tooltip = document.createElement('div');
    tooltip.className = 'mapleclear-tooltip';
    tooltip.innerHTML = `
      <div class="tooltip-content">
        <strong>${expansion.acronym}</strong>: ${expansion.expansion}
        ${expansion.definition ? `<div class="definition">${expansion.definition}</div>` : ''}
        ${expansion.source_url ? `<a href="${expansion.source_url}" target="_blank">More info</a>` : ''}
      </div>
    `;
    
    const rect = element.getBoundingClientRect();
    tooltip.style.position = 'absolute';
    tooltip.style.top = `${rect.bottom + window.scrollY + 5}px`;
    tooltip.style.left = `${rect.left + window.scrollX}px`;
    tooltip.style.zIndex = '10000';
    tooltip.style.background = '#333';
    tooltip.style.color = 'white';
    tooltip.style.padding = '8px 12px';
    tooltip.style.borderRadius = '4px';
    tooltip.style.fontSize = '14px';
    tooltip.style.maxWidth = '300px';
    tooltip.style.boxShadow = '0 2px 8px rgba(0,0,0,0.3)';
    
    document.body.appendChild(tooltip);
  }

  private hideAcronymTooltip(): void {
    const existing = document.querySelector('.mapleclear-tooltip');
    if (existing) {
      existing.remove();
    }
  }

  private async expandAcronym(acronym: string): Promise<void> {
    try {
      const response = await fetch(`${CONFIG.API_BASE}/expand-acronyms`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: acronym })
      });
      
      if (response.ok) {
        const data = await response.json();
        console.log('Acronym expansion:', data);
      }
    } catch (error) {
      console.log('Could not expand acronym:', error);
      alert('MapleClear server not available. Please start the server or click the MapleClear extension icon.');
    }
  }

  private getTextNodes(element: Element): Text[] {
    const textNodes: Text[] = [];
    const walker = document.createTreeWalker(
      element,
      NodeFilter.SHOW_TEXT,
      null
    );
    
    let node;
    while (node = walker.nextNode()) {
      textNodes.push(node as Text);
    }
    
    return textNodes;
  }

  private async createSplitScreen(action: string, language: string, languageName: string): Promise<{ success: boolean; error?: string }> {
    try {
      this.removeSplitScreen();
      
      const mainContent = this.extractMainContentForSplitScreen();
      if (!mainContent) {
        return { success: false, error: 'No content found to process' };
      }

      const splitContainer = document.createElement('div');
      splitContainer.id = 'mapleclear-split-screen';
      splitContainer.className = 'mapleclear-split-screen';
      
      const originalPane = document.createElement('div');
      originalPane.className = 'split-pane original-pane';
      originalPane.innerHTML = `
        <div class="pane-header">
          <h3>📄 Original</h3>
          <button class="close-split" title="Close split view">×</button>
        </div>
        <div class="pane-content">
          ${mainContent}
        </div>
      `;

      const processedPane = document.createElement('div');
      processedPane.className = 'split-pane processed-pane';
      processedPane.innerHTML = `
        <div class="pane-header">
          <h3>${action === 'simplify' ? '✨ Simplified' : `🌍 ${languageName}`}</h3>
          <div class="pane-actions">
            <button class="copy-content" title="Copy content">📋</button>
            <button class="print-content" title="Print">🖨️</button>
          </div>
        </div>
        <div class="pane-content">
          <div class="processing-indicator">
            <div class="spinner"></div>
            <p>Processing content...</p>
          </div>
        </div>
      `;

      splitContainer.appendChild(originalPane);
      splitContainer.appendChild(processedPane);

      document.body.style.overflow = 'hidden';
      const originalContent = document.body.innerHTML;
      document.body.innerHTML = '';
      document.body.appendChild(splitContainer);

      this.setupSplitScreenEventListeners(splitContainer, originalContent);

      await this.processContentForSplitScreen(action, language, mainContent, processedPane);

      return { success: true };

    } catch (error) {
      console.error('Failed to create split screen:', error);
      return { success: false, error: error instanceof Error ? error.message : 'Unknown error' };
    }
  }

  private extractMainContentForSplitScreen(): string {
    const selectors = [
      'main',
      '[role="main"]',
      '.main-content',
      '.content',
      'article',
      '.post-content',
      '.entry-content',
      '#content',
      '.page-content'
    ];

    for (const selector of selectors) {
      const element = document.querySelector(selector);
      if (element?.textContent?.trim().length && element.textContent.trim().length > 100) {
        return element.innerHTML;
      }
    }

    const walker = document.createTreeWalker(
      document.body,
      NodeFilter.SHOW_TEXT,
      null
    );

    const textNodes: string[] = [];
    let node;
    while (node = walker.nextNode()) {
      const text = node.textContent?.trim();
      const whitespaceRegex = /^\s*$/;
      if (text && text.length > 20 && !whitespaceRegex.test(text)) {
        textNodes.push(`<p>${text}</p>`);
      }
    }

    return textNodes.slice(0, 50).join('\n');
  }

  private setupSplitScreenEventListeners(container: HTMLElement, originalContent: string): void {
    const closeButton = container.querySelector('.close-split');
    if (closeButton) {
      closeButton.addEventListener('click', () => {
        this.removeSplitScreen();
        document.body.innerHTML = originalContent;
        document.body.style.overflow = '';
      });
    }

    const copyButton = container.querySelector('.copy-content');
    if (copyButton) {
      copyButton.addEventListener('click', () => {
        const processedContent = container.querySelector('.processed-pane .pane-content');
        if (processedContent) {
          navigator.clipboard.writeText(processedContent.textContent || '').then(() => {
            copyButton.textContent = '✅';
            setTimeout(() => {
              copyButton.textContent = '📋';
            }, 2000);
          });
        }
      });
    }

    const printButton = container.querySelector('.print-content');
    if (printButton) {
      printButton.addEventListener('click', () => {
        const processedContent = container.querySelector('.processed-pane .pane-content');
        if (processedContent) {
          const printWindow = window.open('', '_blank');
          if (printWindow) {
            printWindow.document.body.innerHTML = `
              <h1>🍁 MapleClear - Processed Content</h1>
              ${processedContent.innerHTML}
            `;
            printWindow.print();
          }
        }
      });
    }
  }

  private async processContentForSplitScreen(action: string, language: string, content: string, processedPane: HTMLElement): Promise<void> {
    try {
      const tempDiv = document.createElement('div');
      tempDiv.innerHTML = content;
      const textContent = tempDiv.textContent || tempDiv.innerText || '';

      const endpoint = action === 'simplify' ? '/simplify' : '/translate';
      const requestData = action === 'simplify' 
        ? { text: textContent, target_grade: 7, preserve_acronyms: true }
        : { text: textContent, target_language: language, preserve_terms: true };

      const response = await fetch(`${CONFIG.API_BASE}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestData)
      });

      if (!response.ok) {
        throw new Error(`Server responded with status ${response.status}`);
      }

      const result = await response.json();
      const processedText = result.plain || result.result || result.simplified || result.translated || 'Processing completed';

      const paneContent = processedPane.querySelector('.pane-content');
      if (paneContent) {
        const formattedContent = processedText
          .split('\n')
          .map((line: string) => line.trim())
          .filter((line: string) => line.length > 0)
          .map((line: string) => `<p>${this.escapeHtml(line)}</p>`)
          .join('');

        paneContent.innerHTML = formattedContent || '<p>No content processed</p>';

        this.setupAcronymDetectionInElement(paneContent as HTMLElement);
      }

    } catch (error) {
      console.error('Processing failed:', error);
      const paneContent = processedPane.querySelector('.pane-content');
      if (paneContent) {
        paneContent.innerHTML = `
          <div class="error-message">
            <h3>❌ Processing Error</h3>
            <p>${error instanceof Error ? error.message : 'Unknown error occurred'}</p>
            <p><small>Make sure the MapleClear server is running on port 11434</small></p>
          </div>
        `;
      }
    }
  }

  private setupAcronymDetectionInElement(element: HTMLElement): void {
    const acronymRegex = /\b[A-Z]{2,}\b/g;
    const textNodes = this.getTextNodes(element);
    
    textNodes.forEach((node: Text) => {
      const text = node.textContent || '';
      const matches = Array.from(text.matchAll(acronymRegex));
      
      if (matches.length > 0) {
        let newHTML = text;
        const sortedMatches = [...matches].reverse();
        sortedMatches.forEach((match: RegExpExecArray) => {
          const acronym = match[0];
          const index = match.index ?? 0;
          
          const before = newHTML.substring(0, index);
          const after = newHTML.substring(index + acronym.length);
          
          newHTML = before + `<span class="mapleclear-acronym" data-acronym="${acronym}" title="Hover for definition">${acronym}</span>` + after;
        });
        
        if (node.parentElement && newHTML !== text) {
          const wrapper = document.createElement('span');
          wrapper.innerHTML = newHTML;
          node.parentElement.replaceChild(wrapper, node);
        }
      }
    });
  }

  private removeSplitScreen(): void {
    const existing = document.getElementById('mapleclear-split-screen');
    if (existing) {
      existing.remove();
    }
  }

  private escapeHtml(text: string): string {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  private getPageInfo(): any {
    return {
      url: window.location.href,
      title: document.title,
      domain: window.location.hostname,
      hasSelection: !!this.currentSelection,
      isGovernmentSite: CONFIG.TRIGGER_DOMAINS.some(domain => 
        window.location.hostname.includes(domain)
      )
    };
  }
}

const contentScript = new MapleClearContentScript();
void contentScript.init();
if (contentScript) {
  console.log('Content script loaded');
}
