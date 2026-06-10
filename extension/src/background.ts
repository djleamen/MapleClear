/**
 * MapleClear Background Script (Service Worker)
 * 
 * Handles extension lifecycle, toolbar actions, and coordinate between
 * popup and content scripts.
 */

import browser from 'webextension-polyfill';

const API_BASE = 'http://127.0.0.1:11434';

interface ApiResponse {
  ok: boolean;
  status: number;
  data?: any;
  error?: string;
}

class MapleClearBackground {
  constructor() {
    this.init();
  }

  private init(): void {
    browser.action.onClicked.addListener(this.handleToolbarClick.bind(this));
    browser.runtime.onMessage.addListener(this.handleMessage.bind(this));
    this.setupContextMenus();
    this.startStatusCheck();
    console.log('\u{1F341} MapleClear background script initialized');
  }

  private async handleToolbarClick(tab: browser.Tabs.Tab): Promise<void> {
    if (!tab.id) return;

    try {
      await browser.tabs.sendMessage(tab.id, {
        type: 'TOGGLE_PANEL'
      });
    } catch (error) {
      console.error('Failed to toggle panel:', error);
      
      try {
        await browser.scripting.executeScript({
          target: { tabId: tab.id },
          files: ['content-script.js']
        });
        
        await browser.tabs.sendMessage(tab.id, {
          type: 'TOGGLE_PANEL'
        });
      } catch (injectError) {
        console.error('Failed to inject content script:', injectError);
      }
    }
  }

  private handleMessage(
    message: any, 
    _sender: browser.Runtime.MessageSender
  ): Promise<any> | void {
    switch (message.type) {
      case 'GET_SERVER_STATUS':
        return this.getServerStatus();

      case 'CHECK_PERMISSIONS':
        return this.checkPermissions();

      case 'REQUEST_PERMISSION':
        return this.requestPermission(message.permission);

      case 'API_REQUEST':
        return this.proxyApiRequest(message.endpoint, message.body);

      default:
        console.warn('Unknown message type:', message.type);
    }
  }

  /**
   * Proxy inference-server calls for content scripts. Requests made here
   * carry the extension's origin, so the server can allowlist extension
   * schemes instead of every page origin the content script runs on.
   */
  private async proxyApiRequest(endpoint: unknown, body: unknown): Promise<ApiResponse> {
    if (typeof endpoint !== 'string' || !endpoint.startsWith('/')) {
      return { ok: false, status: 0, error: 'Invalid API endpoint' };
    }

    try {
      const response = await fetch(`${API_BASE}${endpoint}`, {
        method: body === undefined ? 'GET' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: body === undefined ? undefined : JSON.stringify(body),
        signal: AbortSignal.timeout(120000)
      });

      const data = await response.json().catch(() => undefined);
      return { ok: response.ok, status: response.status, data };
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Request failed';
      return { ok: false, status: 0, error: message };
    }
  }

  private setupContextMenus(): void {
    browser.contextMenus.create({
      id: 'mapleclear-simplify',
      title: 'Simplify with MapleClear',
      contexts: ['selection'],
      documentUrlPatterns: [
        'https://*.canada.ca/*',
        'https://*.gc.ca/*',
        'http://localhost:*/*',
        'file:///*'
      ]
    });

    browser.contextMenus.create({
      id: 'mapleclear-translate',
      title: 'Translate with MapleClear',
      contexts: ['selection'],
      documentUrlPatterns: [
        'https://*.canada.ca/*',
        'https://*.gc.ca/*',
        'http://localhost:*/*',
        'file:///*'
      ]
    });

    browser.contextMenus.onClicked.addListener(this.handleContextMenu.bind(this));
  }

  private async handleContextMenu(
    info: browser.Menus.OnClickData,
    tab?: browser.Tabs.Tab
  ): Promise<void> {
    if (!tab?.id) return;

    try {
      switch (info.menuItemId) {
        case 'mapleclear-simplify':
          await browser.tabs.sendMessage(tab.id, {
            type: 'SIMPLIFY_SELECTION'
          });
          break;
        
        case 'mapleclear-translate':
          await browser.tabs.sendMessage(tab.id, {
            type: 'TRANSLATE_TEXT',
            targetLanguage: 'fr'
          });
          break;
      }
    } catch (error) {
      console.error('Context menu action failed:', error);
    }
  }

  private async getServerStatus(): Promise<{
    status: 'connected' | 'disconnected';
    info?: any;
  }> {
    try {
      const response = await fetch(`${API_BASE}/health`, {
        method: 'GET',
        signal: AbortSignal.timeout(5000)
      });

      if (response.ok) {
        const info = await response.json();
        this.updateBadge('connected');
        return { status: 'connected', info };
      } else {
        throw new Error(`HTTP ${response.status}`);
      }
    } catch (error) {
      console.error('Server health check failed:', error);
      this.updateBadge('disconnected');
      return { status: 'disconnected' };
    }
  }

  private updateBadge(status: 'connected' | 'disconnected'): void {
    const badgeText = status === 'connected' ? '' : '!';
    const badgeColor = status === 'connected' ? '#22c55e' : '#ef4444';

    browser.action.setBadgeText({ text: badgeText });
    browser.action.setBadgeBackgroundColor({ color: badgeColor });
    
    const title = status === 'connected' 
      ? 'MapleClear - Connected to local server'
      : 'MapleClear - Server disconnected';
    browser.action.setTitle({ title });
  }

  private startStatusCheck(): void {
    this.getServerStatus();

    setInterval(() => {
      this.getServerStatus();
    }, 30000);
  }

  private async checkPermissions(): Promise<{
    hasActiveTab: boolean;
    hasLocalhost: boolean;
    hasGovernmentSites: boolean;
  }> {
    const permissions = await browser.permissions.getAll();
    
    return {
      hasActiveTab: permissions.permissions?.includes('activeTab') ?? false,
      hasLocalhost: permissions.origins?.some(origin => 
        origin.includes('localhost') || origin.includes('127.0.0.1')
      ) ?? false,
      hasGovernmentSites: permissions.origins?.some(origin => 
        origin.includes('canada.ca') || origin.includes('gc.ca')
      ) ?? false
    };
  }

  private async requestPermission(permission: string): Promise<boolean> {
    try {
      const granted = await browser.permissions.request({
        origins: [permission]
      });
      return granted;
    } catch (error) {
      console.error('Permission request failed:', error);
      return false;
    }
  }
}

const background = new MapleClearBackground();
if (background) {
  console.log('Background script loaded');
}
