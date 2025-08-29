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
    console.log('🍁 MapleClear content script initializing...');
    
    if (!this.shouldActivate()) {
      console.log('🚫 Not activating on this domain:', window.location.hostname);
      return;
    }

    console.log('✅ Activating MapleClear on:', window.location.hostname);
    
    this.injectStyles();
    
    browser.runtime.onMessage.addListener((message: any) => this.handleMessage(message));
    
    document.addEventListener('selectionchange', () => this.handleSelection());
    
    this.setupAcronymDetection();
    
    console.log('🍁 MapleClear content script initialized successfully');
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
    console.log('📨 Content script received message:', message);
    
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
        console.log('🔧 Creating split screen with:', message);
        return this.createSplitScreen(message.action, message.language, message.languageName);
      
      case 'GET_PAGE_INFO':
        return this.getPageInfo();
      
      default:
        console.warn('❓ Unknown message type:', message.type);
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
    if (target?.classList?.contains?.('mapleclear-acronym')) {
      const acronym = target.dataset.acronym;
      if (acronym) {
        await this.showAcronymTooltip(target, acronym);
      }
    }
  }

  private handleAcronymLeave(event: Event): void {
    const target = event.target as HTMLElement;
    if (target?.classList?.contains?.('mapleclear-acronym')) {
      this.hideAcronymTooltip();
    }
  }

  private async handleAcronymClick(event: Event): Promise<void> {
    const target = event.target as HTMLElement;
    if (target?.classList?.contains?.('mapleclear-acronym')) {
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
        } else {
          this.createTooltip(element, this.getDemoAcronymExpansion(acronym));
        }
      } else {
        this.createTooltip(element, this.getDemoAcronymExpansion(acronym));
      }
    } catch (error) {
      console.log('Could not fetch acronym expansion:', error);
      this.createTooltip(element, this.getDemoAcronymExpansion(acronym));
    }
  }

  private getDemoAcronymExpansion(acronym: string): any {
    // Common Canadian government acronyms for demo
    const demoExpansions: { [key: string]: any } = {
      'CBC': {
        acronym: 'CBC',
        expansion: 'Canadian Broadcasting Corporation',
        definition: 'Canada\'s national public broadcaster providing news, entertainment, and information services.'
      },
      'CRA': {
        acronym: 'CRA',
        expansion: 'Canada Revenue Agency',
        definition: 'Federal agency responsible for tax collection and administration of tax laws.'
      },
      'RCMP': {
        acronym: 'RCMP',
        expansion: 'Royal Canadian Mounted Police',
        definition: 'Canada\'s national police service providing federal law enforcement.'
      },
      'EI': {
        acronym: 'EI',
        expansion: 'Employment Insurance',
        definition: 'Government program providing temporary financial assistance to unemployed workers.'
      },
      'CPP': {
        acronym: 'CPP',
        expansion: 'Canada Pension Plan',
        definition: 'Contributory, earnings-related social insurance program providing retirement benefits.'
      },
      'GST': {
        acronym: 'GST',
        expansion: 'Goods and Services Tax',
        definition: 'Federal value-added tax levied on most goods and services sold in Canada.'
      },
      'HST': {
        acronym: 'HST',
        expansion: 'Harmonized Sales Tax',
        definition: 'Combined federal and provincial sales tax used in participating provinces.'
      },
      'SIN': {
        acronym: 'SIN',
        expansion: 'Social Insurance Number',
        definition: 'Nine-digit number required to work in Canada and access government programs.'
      }
    };

    return demoExpansions[acronym] || {
      acronym,
      expansion: 'Expansion not available',
      definition: '🍁 MapleClear can provide definitions when connected to the server. Click the extension icon to get started!'
    };
  }

  private createTooltip(element: HTMLElement, expansion: any): void {
    const tooltip = document.createElement('div');
    tooltip.className = 'mapleclear-tooltip';
    tooltip.innerHTML = `
      <div class="tooltip-content">
        <strong>${expansion.acronym}</strong>
        ${expansion.expansion}
        ${expansion.definition ? `<div class="definition">${expansion.definition}</div>` : ''}
        ${expansion.source_url ? `<a href="${expansion.source_url}" target="_blank">More info →</a>` : ''}
      </div>
    `;
    
    const rect = element.getBoundingClientRect();
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;
    
    // Add tooltip to DOM first to measure its dimensions
    tooltip.style.position = 'absolute';
    tooltip.style.visibility = 'hidden';
    document.body.appendChild(tooltip);
    
    const tooltipRect = tooltip.getBoundingClientRect();
    const tooltipWidth = tooltipRect.width;
    const tooltipHeight = tooltipRect.height;
    
    // Calculate optimal position
    let top = rect.bottom + window.scrollY + 8;
    let left = rect.left + window.scrollX;
    
    // Adjust horizontal position to stay within viewport
    if (left + tooltipWidth > viewportWidth - 20) {
      left = viewportWidth - tooltipWidth - 20;
    }
    if (left < 20) {
      left = 20;
    }
    
    // Adjust vertical position if tooltip would go below viewport
    if (rect.bottom + tooltipHeight > viewportHeight - 20) {
      top = rect.top + window.scrollY - tooltipHeight - 8;
    }
    
    // Final positioning
    tooltip.style.top = `${top}px`;
    tooltip.style.left = `${left}px`;
    tooltip.style.visibility = 'visible';
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
      console.log('🔧 Creating split screen:', { action, language, languageName });
      this.removeSplitScreen();
      
      const mainContent = this.extractMainContentForSplitScreen();
      console.log('📄 Extracted main content length:', mainContent?.length || 0);
      
      if (!mainContent) {
        console.error('❌ No content found to process');
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
            <h3>🍁 MapleClear is working...</h3>
            <p>${action === 'simplify' ? 'Simplifying your content into plain language' : `Translating to ${languageName}`}</p>
            <ul class="processing-steps">
              <li>Analyzing content structure</li>
              <li>Processing with AI</li>
              <li>Applying Canadian government style</li>
              <li>Detecting acronyms for tooltips</li>
            </ul>
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

      console.log('🔧 Processing content for split screen:', { action, language, contentLength: textContent.length });

      const endpoint = action === 'simplify' ? '/simplify' : '/translate';
      const requestData = action === 'simplify' 
        ? { text: textContent, target_grade: 7, preserve_acronyms: true }
        : { text: textContent, target_language: language, preserve_terms: true };

      console.log('🚀 Making API request to:', `${CONFIG.API_BASE}${endpoint}`);

      const response = await fetch(`${CONFIG.API_BASE}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestData)
      });

      if (!response.ok) {
        throw new Error(`Server responded with status ${response.status}`);
      }

      const result = await response.json();
      console.log('📦 API response received:', result);

      let processedText = '';
      
      // Handle different response types
      if (result.plain && result.plain.trim()) {
        processedText = result.plain;
        console.log('✅ Using result.plain:', processedText.substring(0, 100) + '...');
      } else if (result.translated !== undefined) {
        processedText = result.translated || 'Translation completed but no content returned';
        console.log('✅ Using result.translated:', processedText.substring(0, 100) + '...');
      } else if (result.result) {
        processedText = result.result;
        console.log('✅ Using result.result:', processedText.substring(0, 100) + '...');
      } else if (result.simplified) {
        processedText = result.simplified;
        console.log('✅ Using result.simplified:', processedText.substring(0, 100) + '...');
      } else {
        // Fallback: show the raw JSON response for debugging
        processedText = `Debug: ${JSON.stringify(result, null, 2)}`;
        console.log('⚠️ No recognized content field in response, showing raw response');
      }

      const paneContent = processedPane.querySelector('.pane-content');
      if (paneContent) {
        console.log('🎨 Formatting content for display...');
        console.log('🔍 Raw processedText:', processedText);
        
        // Simplify content formatting - just use the text directly with minimal processing
        let finalContent = '';
        if (processedText?.trim()) {
          // Even simpler approach: just put the text directly with basic styling
          finalContent = `<div style="color: #000000 !important; font-size: 18px !important; line-height: 1.6 !important; padding: 20px !important; background: #ffffff !important; border: 2px solid red !important;">${processedText.replace(/\n/g, '<br>')}</div>`;
        } else {
          finalContent = '<div style="color: #ff0000 !important; font-size: 18px !important; background: #ffff00 !important; padding: 20px !important; border: 2px solid red !important;"><em>No content was returned from the server</em></div>';
        }

        console.log('📝 Final formatted content length:', finalContent.length);
        console.log('📝 Final formatted content preview:', finalContent.substring(0, 300));
        
        // Clear any existing content first
        paneContent.innerHTML = '';
        console.log('🎨 Cleared existing content');
        
        // Set the new content
        paneContent.innerHTML = finalContent;
        console.log('🎨 Set new content, innerHTML length:', paneContent.innerHTML.length);
        
        // Force visible styling with maximum specificity
        const htmlElement = paneContent as HTMLElement;
        htmlElement.style.cssText = `
          color: #343a40 !important;
          font-size: 16px !important;
          line-height: 1.7 !important;
          visibility: visible !important;
          display: block !important;
          opacity: 1 !important;
          background-color: white !important;
          min-height: 100px !important;
          width: 100% !important;
          overflow: visible !important;
          position: relative !important;
          z-index: 1 !important;
        `;
        console.log('🎨 Applied styling');
        
        // Force all child elements to be visible
        const allElements = htmlElement.querySelectorAll('*');
        allElements.forEach((el: Element) => {
          const element = el as HTMLElement;
          element.style.cssText = `
            color: #343a40 !important;
            visibility: visible !important;
            display: block !important;
            opacity: 1 !important;
          `;
        });
        console.log('🎨 Forced visibility on', allElements.length, 'child elements');
        
        console.log('🎨 Content set, pane content innerHTML length:', paneContent.innerHTML.length);
        console.log('🎨 Pane content text content:', paneContent.textContent?.substring(0, 200));

        this.setupAcronymDetectionInElement(paneContent as HTMLElement);
        console.log('✅ Content displayed and acronym detection set up');
      } else {
        console.error('❌ Could not find pane content element');
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

    // Add event listeners specifically for this element
    element.addEventListener('mouseenter', async (event) => {
      const target = event.target as HTMLElement;
      if (target?.classList.contains('mapleclear-acronym')) {
        const acronym = target.dataset.acronym;
        if (acronym) {
          await this.showAcronymTooltip(target, acronym);
        }
      }
    }, true);

    element.addEventListener('mouseleave', (event) => {
      const target = event.target as HTMLElement;
      if (target?.classList.contains('mapleclear-acronym')) {
        this.hideAcronymTooltip();
      }
    }, true);

    element.addEventListener('click', async (event) => {
      const target = event.target as HTMLElement;
      if (target?.classList.contains('mapleclear-acronym')) {
        event.preventDefault();
        const acronym = target.dataset.acronym;
        if (acronym) {
          await this.expandAcronym(acronym);
        }
      }
    }, true);
  }

  private removeSplitScreen(): void {
    const existing = document.getElementById('mapleclear-split-screen');
    if (existing) {
      existing.remove();
    }
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
