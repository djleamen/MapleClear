/**
 * MapleClear Popup Script - Streamlined Version
 * 
 * Handles the extension popup interface with simplified UI flow:
 * 1. Click extension icon
 * 2. Choose "Simplify" or "Translate"
 * 3. If translate, select language from dropdown
 * 4. Page splits side-by-side with original (left) and processed (right)
 */

class MapleClearPopup {
  constructor() {
    this.selectedAction = null;
    this.selectedLanguage = null;
    this.currentStep = 'action-selector';
    this.serverStatus = 'unknown';
    
    this.init();
  }

  async init() {
    await this.checkServerStatus();
    this.setupEventListeners();
    this.updatePageInfo();
    this.showStep('action-selector');
  }

  setupEventListeners() {
    document.querySelectorAll('[data-action]').forEach(button => {
      button.addEventListener('click', (e) => {
        this.selectAction(e.target.closest('[data-action]').dataset.action);
      });
    });

    document.querySelectorAll('[data-lang]').forEach(button => {
      button.addEventListener('click', (e) => {
        const langElement = e.target.closest('[data-lang]');
        this.selectLanguage(langElement.dataset.lang, langElement.dataset.name);
      });
    });

    document.getElementById('back-button')?.addEventListener('click', () => {
      this.showStep('action-selector');
    });

    document.getElementById('help-link')?.addEventListener('click', (e) => {
      e.preventDefault();
      if (window.confirm('You are about to open an external site (GitHub). Continue?')) {
        browser.tabs.create({ url: 'https://github.com/djleamen/MapleClear#readme' });
      }
    });

    document.getElementById('feedback-link')?.addEventListener('click', (e) => {
      e.preventDefault();
      browser.tabs.create({ url: 'https://github.com/djleamen/MapleClear/issues' });
    });
  }

  async checkServerStatus() {
    try {
      const response = await fetch('http://127.0.0.1:11434/health');
      if (response.ok) {
        const data = await response.json();
        this.serverStatus = 'connected';
        this.updateStatus('connected', `${data.backend} backend ready`);
      } else {
        throw new Error('Server not responding');
      }
    } catch (error) {
      console.error('Failed to connect to MapleClear server:', error);
      this.serverStatus = 'disconnected';
      this.updateStatus('disconnected', 'Server offline - Please start MapleClear server');
    }
  }

  updateStatus(status, message) {
    const indicator = document.getElementById('status-indicator');
    const text = document.getElementById('status-text');
    
    if (indicator) {
      indicator.className = `status-indicator ${status}`;
    }
    if (text) {
      text.textContent = message;
    }
  }

  updatePageInfo() {
    browser.tabs.query({ active: true, currentWindow: true }).then(tabs => {
      const tab = tabs[0];
      const domain = new URL(tab.url).hostname;
      
      const domainElement = document.getElementById('current-domain');
      if (domainElement) {
        domainElement.textContent = domain;
      }
    });
  }

  selectAction(action) {
    this.selectedAction = action;
    
    document.querySelectorAll('[data-action]').forEach(btn => {
      btn.classList.remove('selected');
    });
    document.querySelector(`[data-action="${action}"]`).classList.add('selected');

    if (action === 'simplify') {
      this.processPage();
    } else if (action === 'translate') {
      this.showStep('language-selector');
    }
  }

  selectLanguage(lang, name) {
    this.selectedLanguage = { code: lang, name: name };
    
    document.querySelectorAll('[data-lang]').forEach(btn => {
      btn.classList.remove('selected');
    });
    document.querySelector(`[data-lang="${lang}"]`).classList.add('selected');
    
    setTimeout(() => {
      this.processPage();
    }, 300);
  }

  showStep(step) {
    this.currentStep = step;
    
    document.querySelectorAll('.action-selector, .language-selector, .processing-status').forEach(el => {
      el.classList.add('hidden');
    });
    
    const section = document.getElementById(step);
    if (section) {
      section.classList.remove('hidden');
    }
  }

  async processPage() {
    this.showStep('processing-status');
    
    const processingText = document.getElementById('processing-text');
    if (processingText) {
      if (this.selectedAction === 'simplify') {
        processingText.textContent = 'Simplifying page content...';
      } else if (this.selectedAction === 'translate') {
        processingText.textContent = `Translating to ${this.selectedLanguage.name}...`;
      }
    }

    try {
      const tabs = await browser.tabs.query({ active: true, currentWindow: true });
      const tab = tabs[0];

      if (!tab) {
        throw new Error('No active tab found');
      }

      if (this.serverStatus === 'disconnected') {
        throw new Error('MapleClear server is not running');
      }

      const response = await browser.tabs.sendMessage(tab.id, {
        type: 'CREATE_SPLIT_SCREEN',
        action: this.selectedAction,
        language: this.selectedLanguage?.code || 'en',
        languageName: this.selectedLanguage?.name || 'English'
      });

      if (response && response.success) {
        window.close();
      } else {
        throw new Error(response?.error || 'Failed to create split screen');
      }

    } catch (error) {
      console.error('Processing failed:', error);
      this.showError(error.message);
    }
  }

  showError(message) {
    const processingText = document.getElementById('processing-text');
    if (processingText) {
      processingText.textContent = '❌ Error';
    }

    const processingDetail = document.querySelector('.processing-detail');
    if (processingDetail) {
      processingDetail.textContent = message;
      processingDetail.style.color = '#dc3545';
    }

    const spinner = document.querySelector('.spinner');
    if (spinner) {
      spinner.style.display = 'none';
    }

    setTimeout(() => {
      this.showStep('action-selector');
      this.selectedAction = null;
      this.selectedLanguage = null;
    }, 3000);
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    window.mapleClearPopup = new MapleClearPopup();
  });
} else {
  window.mapleClearPopup = new MapleClearPopup();
}

const style = document.createElement('style');
style.textContent = `
  @keyframes slideDown {
    from {
      transform: translateX(-50%) translateY(-20px);
      opacity: 0;
    }
    to {
      transform: translateX(-50%) translateY(0);
      opacity: 1;
    }
  }
  
  .action-button.selected,
  .language-button.selected {
    background: #007bff !important;
    color: white !important;
    border-color: #007bff !important;
    transform: scale(0.98);
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

  .status-indicator.connected {
    background: #28a745;
  }

  .status-indicator.disconnected {
    background: #dc3545;
  }

  .hidden {
    display: none !important;
  }
`;
document.head.appendChild(style);
