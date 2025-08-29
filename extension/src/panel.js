/**
 * Panel functionality for MapleClear extension
 */

class MapleClearPanel {
  constructor() {
    this.originalContent = '';
    this.improvedContent = '';
    this.currentView = 'single';
    this.currentAction = null;
    
    this.init();
  }

  init() {
    this.setupEventListeners();
    this.updateSelectionInfo();
    this.checkServerStatus();
  }

  setupEventListeners() {
    const closeButton = document.querySelector('.close-button');
    if (closeButton) {
      closeButton.addEventListener('click', () => this.closePanel());
    }

    document.getElementById('simplify-selection')?.addEventListener('click', () => 
      this.handleAction('simplify-selection'));
    document.getElementById('simplify-page')?.addEventListener('click', () => 
      this.handleAction('simplify-page'));
    document.getElementById('translate')?.addEventListener('click', () => 
      this.handleAction('translate'));
    document.getElementById('translate-indigenous')?.addEventListener('click', () => 
      this.handleAction('translate-indigenous'));

    document.getElementById('toggle-view')?.addEventListener('click', () => 
      this.toggleView());

    document.getElementById('copy-result')?.addEventListener('click', () => 
      this.copyResult());
    document.getElementById('print-result')?.addEventListener('click', () => 
      this.printResult());
    document.getElementById('new-action')?.addEventListener('click', () => 
      this.newAction());

    const indigenousCheckbox = document.getElementById('enable-indigenous');
    if (indigenousCheckbox) {
      indigenousCheckbox.addEventListener('change', (e) => {
        const options = document.getElementById('indigenous-options');
        if (options) {
          options.classList.toggle('hidden', !e.target.checked);
        }
      });
    }

    document.addEventListener('selectionchange', () => this.updateSelectionInfo());
  }

  closePanel() {
    if (window.parent !== window) {
      window.parent.postMessage({ type: 'closePanel' }, '*');
    }
  }

  updateSelectionInfo() {
    const selection = window.getSelection();
    const selectionInfo = document.querySelector('.selection-info');
    
    if (!selectionInfo) return;

    if (selection && selection.toString().trim()) {
      const text = selection.toString().trim();
      const wordCount = text.split(/\s+/).length;
      selectionInfo.textContent = `Selected: ${wordCount} word${wordCount !== 1 ? 's' : ''}`;
      selectionInfo.classList.remove('hidden');
      selectionInfo.classList.add('has-selection');
    } else {
      selectionInfo.textContent = 'No text selected';
      selectionInfo.classList.add('hidden');
      selectionInfo.classList.remove('has-selection');
    }
  }

  async checkServerStatus() {
    try {
      const response = await fetch('http://127.0.0.1:11434/health');
      const data = await response.json();
      
      this.updateServerStatus(true, data);
    } catch (error) {
      console.error('Server status check failed:', error);
      this.updateServerStatus(false);
    }
  }

  updateServerStatus(connected, data = null) {
    const statusElements = document.querySelectorAll('.status-indicator');
    statusElements.forEach(el => {
      el.className = `status-indicator ${connected ? 'connected' : 'error'}`;
    });

    const helpText = document.querySelector('.help-text');
    if (helpText && !connected) {
      helpText.innerHTML = `
        <p>⚠️ <strong>Server not running</strong></p>
        <p>Make sure the MapleClear server is running on port 11434.</p>
        <p>Try: <code>cd /path/to/MapleClear && python -m uvicorn server.app:app --host 127.0.0.1 --port 11434</code></p>
      `;
    }
  }

  async handleAction(actionType) {
    this.currentAction = actionType;
    
    try {
      const textToProcess = this.getTextToProcess(actionType);
      if (!textToProcess) return;

      this.originalContent = textToProcess;
      this.showProcessing();

      const targetLanguage = this.getTargetLanguage(actionType);
      const result = await this.callServer(actionType, textToProcess, targetLanguage);
      
      this.improvedContent = this.extractContentFromResult(result);
      this.showResults(result);

    } catch (error) {
      console.error('Action failed:', error);
      this.showError(`Failed to ${actionType.replace('-', ' ')}: ${error.message}`);
    }
  }

  getTextToProcess(actionType) {
    if (actionType === 'simplify-selection') {
      const selection = window.getSelection();
      const textToProcess = selection ? selection.toString().trim() : '';
      
      if (!textToProcess) {
        this.showError('Please select some text first.');
        return null;
      }
      return textToProcess;
    }
    
    if (actionType === 'simplify-page') {
      return this.extractMainContent();
    }

    const textToProcess = this.extractMainContent();
    if (!textToProcess) {
      this.showError('No text found to process.');
      return null;
    }
    return textToProcess;
  }

  getTargetLanguage(actionType) {
    if (actionType === 'translate') {
      const translateSelect = document.getElementById('translate-select');
      return translateSelect?.value || 'fr';
    }
    
    if (actionType === 'translate-indigenous') {
      const indigenousSelect = document.getElementById('indigenous-select');
      return indigenousSelect?.value || 'iu';
    }
    
    return 'en';
  }

  extractContentFromResult(result) {
    if (result.plain && result.plain.trim()) {
      return result.plain;
    }
    if (result.translated !== undefined) {
      return result.translated || 'Translation completed but no content returned';
    }
    if (result.result) {
      return result.result;
    }
    if (result.simplified) {
      return result.simplified;
    }
    return 'Processing completed but no content returned';
  }

  extractMainContent() {
    const selectors = [
      'main',
      '[role="main"]',
      '.main-content',
      '.content',
      'article',
      '.post-content',
      '.entry-content'
    ];

    for (const selector of selectors) {
      const element = document.querySelector(selector);
      if (element) {
        return element.textContent?.trim() || '';
      }
    }

    const paragraphs = Array.from(document.querySelectorAll('p'))
      .map(p => p.textContent?.trim())
      .filter(text => text && text.length > 50)
      .join('\n\n');

    return paragraphs || document.body.textContent?.trim() || '';
  }

  async callServer(action, text, language = 'en') {
    const endpoint = this.getEndpoint(action);
    
    const requestData = {
      text: text,
      target_language: language,
      preserve_terms: true
    };

    const response = await fetch(`http://127.0.0.1:11434${endpoint}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(requestData)
    });

    if (!response.ok) {
      throw new Error(`Server responded with status ${response.status}`);
    }

    return await response.json();
  }

  getEndpoint(action) {
    switch (action) {
      case 'simplify-selection':
      case 'simplify-page':
        return '/simplify';
      case 'translate':
        return '/translate';
      case 'translate-indigenous':
        return '/translate';
      default:
        return '/simplify';
    }
  }

  showProcessing() {
    this.hideAllSections();
    const resultsContainer = document.querySelector('.results-container');
    if (resultsContainer) {
      resultsContainer.classList.remove('hidden');
      
      const resultContent = document.querySelector('.result-content');
      if (resultContent) {
        resultContent.innerHTML = `
          <div class="processing-indicator">
            <div class="spinner"></div>
            <p>Processing your request...</p>
            <p class="processing-detail">This may take a few moments</p>
          </div>
        `;
      }
    }
  }

  showResults(result) {
    const resultsContainer = document.querySelector('.results-container');
    if (!resultsContainer) return;

    resultsContainer.classList.remove('hidden');
    this.updateResultContent();
    this.updateMetadata(result);
    
    const viewToggle = document.querySelector('.view-toggle');
    if (viewToggle) {
      viewToggle.classList.remove('hidden');
    }
  }

  updateResultContent() {
    if (this.currentView === 'comparison') {
      this.showComparisonView();
    } else {
      this.showSingleView();
    }
  }

  showSingleView() {
    const comparisonView = document.querySelector('.comparison-view');
    const singleView = document.querySelector('.single-view');
    
    if (comparisonView) comparisonView.classList.add('hidden');
    if (singleView) {
      singleView.classList.remove('hidden');
      
      const resultContent = singleView.querySelector('.result-content');
      if (resultContent) {
        resultContent.innerHTML = this.formatContent(this.improvedContent);
      }
    }

    const toggleButton = document.getElementById('toggle-view');
    if (toggleButton) {
      toggleButton.textContent = '📖 Side-by-Side View';
    }
  }

  showComparisonView() {
    const comparisonView = document.querySelector('.comparison-view');
    const singleView = document.querySelector('.single-view');
    
    if (singleView) singleView.classList.add('hidden');
    if (comparisonView) {
      comparisonView.classList.remove('hidden');
      
      const originalContent = comparisonView.querySelector('.original-content');
      const improvedContent = comparisonView.querySelector('.improved-content');
      
      if (originalContent) {
        originalContent.innerHTML = this.formatContent(this.originalContent);
      }
      if (improvedContent) {
        improvedContent.innerHTML = this.formatContent(this.improvedContent);
      }
    }

    const toggleButton = document.getElementById('toggle-view');
    if (toggleButton) {
      toggleButton.textContent = '📄 Single View';
    }
  }

  formatContent(content) {
    return content
      .split('\n')
      .map(line => line.trim())
      .filter(line => line.length > 0)
      .map(line => `<p>${this.escapeHtml(line)}</p>`)
      .join('');
  }

  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  updateMetadata(result) {
    if (result.rationale && Array.isArray(result.rationale)) {
      const rationaleSection = document.querySelector('.rationale-section');
      const rationaleList = document.querySelector('.rationale-list');
      
      if (rationaleSection && rationaleList) {
        rationaleList.innerHTML = result.rationale
          .map(item => `<li>${this.escapeHtml(item)}</li>`)
          .join('');
        rationaleSection.classList.remove('hidden');
      }
    }

    if (result.cautions && Array.isArray(result.cautions)) {
      const cautionsSection = document.querySelector('.cautions-section');
      const cautionsList = document.querySelector('.cautions-list');
      
      if (cautionsSection && cautionsList) {
        cautionsList.innerHTML = result.cautions
          .map(item => `<li>${this.escapeHtml(item)}</li>`)
          .join('');
        cautionsSection.classList.remove('hidden');
      }
    }
  }

  toggleView() {
    this.currentView = this.currentView === 'single' ? 'comparison' : 'single';
    this.updateResultContent();
  }

  async copyResult() {
    try {
      await navigator.clipboard.writeText(this.improvedContent);
      this.showNotification('Content copied to clipboard!');
    } catch (error) {
      console.error('Failed to copy:', error);
      this.showNotification('Failed to copy content', 'error');
    }
  }

  printResult() {
    const printWindow = window.open('', '_blank');
    if (printWindow) {
      printWindow.document.write(`
        <html>
          <head>
            <title>MapleClear Result</title>
            <style>
              body { font-family: Arial, sans-serif; line-height: 1.6; margin: 20px; }
              h1 { color: #333; border-bottom: 2px solid #dc3545; }
              .comparison { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
              .pane { border: 1px solid #ddd; padding: 15px; }
              .pane h2 { margin-top: 0; color: #666; }
            </style>
          </head>
          <body>
            <h1>🍁 MapleClear Result</h1>
            ${this.currentView === 'comparison' ? `
              <div class="comparison">
                <div class="pane">
                  <h2>Original</h2>
                  ${this.formatContent(this.originalContent)}
                </div>
                <div class="pane">
                  <h2>Improved</h2>
                  ${this.formatContent(this.improvedContent)}
                </div>
              </div>
            ` : `
              <div>
                ${this.formatContent(this.improvedContent)}
              </div>
            `}
          </body>
        </html>
      `);
      printWindow.document.close();
      printWindow.print();
    }
  }

  newAction() {
    this.hideAllSections();
    this.originalContent = '';
    this.improvedContent = '';
    this.currentAction = null;
    this.currentView = 'single';
  }

  hideAllSections() {
    const sections = ['.results-container', '.view-toggle'];
    sections.forEach(selector => {
      const element = document.querySelector(selector);
      if (element) element.classList.add('hidden');
    });
  }

  showError(message) {
    const resultsContainer = document.querySelector('.results-container');
    if (resultsContainer) {
      resultsContainer.classList.remove('hidden');
      
      const resultContent = document.querySelector('.result-content');
      if (resultContent) {
        resultContent.innerHTML = `
          <div class="error-message">
            <h3>❌ Error</h3>
            <p>${this.escapeHtml(message)}</p>
            <button onclick="mapleClearPanel.newAction()" class="primary-button">Try Again</button>
          </div>
        `;
      }
    }
  }

  showNotification(message, type = 'success') {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;
    notification.style.cssText = `
      position: fixed;
      top: 20px;
      right: 20px;
      background: ${type === 'error' ? '#dc3545' : '#28a745'};
      color: white;
      padding: 12px 20px;
      border-radius: 6px;
      box-shadow: 0 4px 8px rgba(0,0,0,0.2);
      z-index: 10000;
      font-size: 14px;
    `;

    document.body.appendChild(notification);

    setTimeout(() => {
      notification.remove();
    }, 3000);
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    window.mapleClearPanel = new MapleClearPanel();
  });
} else {
  window.mapleClearPanel = new MapleClearPanel();
}

const style = document.createElement('style');
style.textContent = `
  .processing-indicator {
    text-align: center;
    padding: 40px 20px;
  }

  .spinner {
    border: 3px solid #f3f3f3;
    border-top: 3px solid #dc3545;
    border-radius: 50%;
    width: 40px;
    height: 40px;
    animation: spin 1s linear infinite;
    margin: 0 auto 20px;
  }

  @keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }

  .processing-detail {
    font-size: 12px;
    color: #666;
  }

  .error-message {
    text-align: center;
    padding: 40px 20px;
    color: #dc3545;
  }

  .error-message h3 {
    margin-bottom: 15px;
  }

  .error-message button {
    margin-top: 20px;
  }

  .notification {
    animation: slideIn 0.3s ease-out;
  }

  @keyframes slideIn {
    from {
      transform: translateX(100%);
      opacity: 0;
    }
    to {
      transform: translateX(0);
      opacity: 1;
    }
  }
`;
document.head.appendChild(style);
