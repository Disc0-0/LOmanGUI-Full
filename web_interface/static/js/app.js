/**
 * Last Oasis Manager - Main JavaScript
 * Common functionality for the web interface
 */

// Initialize when DOM is fully loaded
document.addEventListener('DOMContentLoaded', function() {
    initNavigation();
    initTooltips();
    initToasts();
    handleFormSubmissions();
});

/**
 * Global API utilities
 */
const API = {
    /**
     * Make a GET request to the API
     * @param {string} endpoint - API endpoint to call
     * @param {object} options - Additional fetch options
     * @returns {Promise} - Promise resolving to JSON response
     */
    get: async function(endpoint, options = {}) {
        UI.showLoading();
        try {
            const response = await fetch(endpoint, {
                method: 'GET',
                headers: {
                    'Accept': 'application/json',
                },
                ...options
            });
            
            if (!response.ok) {
                throw new Error(`API error: ${response.status} ${response.statusText}`);
            }
            
            return await response.json();
        } catch (error) {
            ErrorHandler.handle(error);
            throw error;
        } finally {
            UI.hideLoading();
        }
    },
    
    /**
     * Make a POST request to the API
     * @param {string} endpoint - API endpoint to call
     * @param {object} data - Data to send in the request body
     * @param {object} options - Additional fetch options
     * @returns {Promise} - Promise resolving to JSON response
     */
    post: async function(endpoint, data = {}, options = {}) {
        UI.showLoading();
        try {
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                },
                body: JSON.stringify(data),
                ...options
            });
            
            if (!response.ok) {
                throw new Error(`API error: ${response.status} ${response.statusText}`);
            }
            
            return await response.json();
        } catch (error) {
            ErrorHandler.handle(error);
            throw error;
        } finally {
            UI.hideLoading();
        }
    },
    
    /**
     * Upload file(s) to the API
     * @param {string} endpoint - API endpoint to call
     * @param {FormData} formData - FormData object containing files
     * @param {object} options - Additional fetch options
     * @returns {Promise} - Promise resolving to JSON response
     */
    upload: async function(endpoint, formData, options = {}) {
        UI.showLoading();
        try {
            const response = await fetch(endpoint, {
                method: 'POST',
                body: formData,
                ...options
            });
            
            if (!response.ok) {
                throw new Error(`API error: ${response.status} ${response.statusText}`);
            }
            
            return await response.json();
        } catch (error) {
            ErrorHandler.handle(error);
            throw error;
        } finally {
            UI.hideLoading();
        }
    }
};

/**
 * Error handling
 */
const ErrorHandler = {
    /**
     * Handle errors by displaying them to the user
     * @param {Error} error - Error object
     */
    handle: function(error) {
        console.error('Error:', error);
        UI.showToast('error', 'Error', error.message || 'An unexpected error occurred');
    }
};

/**
 * UI utilities
 */
const UI = {
    /**
     * Show the loading spinner
     */
    showLoading: function() {
        // Create loading overlay if it doesn't exist
        if (!document.getElementById('loading-overlay')) {
            const overlay = document.createElement('div');
            overlay.id = 'loading-overlay';
            overlay.className = 'position-fixed top-0 start-0 w-100 h-100 d-flex justify-content-center align-items-center bg-dark bg-opacity-25';
            overlay.style.zIndex = '9999';
            overlay.innerHTML = `
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
            `;
            document.body.appendChild(overlay);
        } else {
            document.getElementById('loading-overlay').style.display = 'flex';
        }
    },
    
    /**
     * Hide the loading spinner
     */
    hideLoading: function() {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) {
            overlay.style.display = 'none';
        }
    },
    
    /**
     * Show a toast notification
     * @param {string} type - Type of toast (success, error, warning, info)
     * @param {string} title - Toast title
     * @param {string} message - Toast message
     */
    showToast: function(type, title, message) {
        // Create toast container if it doesn't exist
        if (!document.getElementById('toast-container')) {
            const container = document.createElement('div');
            container.id = 'toast-container';
            container.className = 'position-fixed bottom-0 end-0 p-3';
            container.style.zIndex = '9999';
            document.body.appendChild(container);
        }
        
        // Create a unique ID for this toast
        const toastId = 'toast-' + Date.now();
        
        // Set icon and class based on type
        let icon, bgClass;
        switch (type) {
            case 'success':
                icon = 'fa-check-circle';
                bgClass = 'bg-success';
                break;
            case 'error':
                icon = 'fa-exclamation-circle';
                bgClass = 'bg-danger';
                break;
            case 'warning':
                icon = 'fa-exclamation-triangle';
                bgClass = 'bg-warning';
                break;
            case 'info':
            default:
                icon = 'fa-info-circle';
                bgClass = 'bg-info';
                break;
        }
        
        // Create toast HTML
        const toastHtml = `
            <div id="${toastId}" class="toast" role="alert" aria-live="assertive" aria-atomic="true" data-bs-autohide="true" data-bs-delay="5000">
                <div class="toast-header ${bgClass} text-white">
                    <i class="fas ${icon} me-2"></i>
                    <strong class="me-auto">${title}</strong>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast" aria-label="Close"></button>
                </div>
                <div class="toast-body">
                    ${message}
                </div>
            </div>
        `;
        
        // Add toast to container
        document.getElementById('toast-container').insertAdjacentHTML('beforeend', toastHtml);
        
        // Initialize and show the toast
        const toastElement = document.getElementById(toastId);
        const toast = new bootstrap.Toast(toastElement);
        toast.show();
        
        // Remove toast from DOM after it's hidden
        toastElement.addEventListener('hidden.bs.toast', function() {
            toastElement.remove();
        });
    },
    
    /**
     * Confirm an action with the user
     * @param {string} message - Confirmation message
     * @param {string} title - Modal title
     * @param {Function} onConfirm - Function to call if user confirms
     * @param {string} confirmText - Text for confirm button
     * @param {string} cancelText - Text for cancel button
     */
    confirm: function(message, title = 'Confirm Action', onConfirm, confirmText = 'Confirm', cancelText = 'Cancel') {
        // Create confirmation modal if it doesn't exist
        if (!document.getElementById('confirm-modal')) {
            const modal = document.createElement('div');
            modal.id = 'confirm-modal';
            modal.className = 'modal fade';
            modal.tabIndex = '-1';
            modal.setAttribute('aria-hidden', 'true');
            modal.innerHTML = `
                <div class="modal-dialog modal-dialog-centered">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Confirm Action</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                        </div>
                        <div class="modal-body">
                            <p id="confirm-message">Are you sure?</p>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal" id="confirm-cancel">Cancel</button>
                            <button type="button" class="btn btn-primary" id="confirm-ok">Confirm</button>
                        </div>
                    </div>
                </div>
            `;
            document.body.appendChild(modal);
        }
        
        // Update modal content
        document.querySelector('#confirm-modal .modal-title').textContent = title;
        document.getElementById('confirm-message').textContent = message;
        document.getElementById('confirm-ok').textContent = confirmText;
        document.getElementById('confirm-cancel').textContent = cancelText;
        
        // Setup event handlers
        const modalElement = document.getElementById('confirm-modal');
        const confirmButton = document.getElementById('confirm-ok');
        
        // Remove existing event listeners
        const newConfirmButton = confirmButton.cloneNode(true);
        confirmButton.parentNode.replaceChild(newConfirmButton, confirmButton);
        
        // Add new event listener
        newConfirmButton.addEventListener('click', function() {
            const modal = bootstrap.Modal.getInstance(modalElement);
            modal.hide();
            if (typeof onConfirm === 'function') {
                onConfirm();
            }
        });
        
        // Show the modal
        const modal = new bootstrap.Modal(modalElement);
        modal.show();
    }
};

/**
 * Dashboard functionality
 */
const Dashboard = {
    /**
     * Refresh the dashboard data
     */
    refresh: async function() {
        try {
            const data = await API.get('/api/dashboard');
            
            // Update last refresh time
            const refreshTime = new Date().toLocaleTimeString();
            const refreshElement = document.getElementById('last-update-time');
            if (refreshElement) {
                refreshElement.textContent = refreshTime;
            }
            
            // Update server status if the function exists
            if (typeof updateServerStatus === 'function') {
                updateServerStatus(data.servers);
            }
            
            // Update mod status if the function exists
            if (typeof updateModStatus === 'function') {
                updateModStatus(data.mods);
            }
            
            // Update system status if the function exists
            if (typeof updateSystemStatus === 'function') {
                updateSystemStatus(data.system);
            }
            
            return data;
        } catch (error) {
            console.error('Failed to refresh dashboard:', error);
            return null;
        }
    },
    
    /**
     * Set up auto-refresh for the dashboard
     * @param {number} interval - Refresh interval in milliseconds
     */
    startAutoRefresh: function(interval = 60000) {
        // Clear any existing interval
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
        }
        
        // Set up new interval
        this.refreshInterval = setInterval(() => {
            this.refresh();
        }, interval);
        
        // Initial refresh
        this.refresh();
    },
    
    /**
     * Stop auto-refresh for the dashboard
     */
    stopAutoRefresh: function() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
        }
    }
};

/**
 * Initialize navigation
 */
function initNavigation() {
    // Set active nav item based on current URL
    const currentPath = window.location.pathname;
    const navLinks = document.querySelectorAll('.navbar-nav .nav-link');
    
    navLinks.forEach(link => {
        // Remove any existing active classes
        link.classList.remove('active');
        
        // Get the path from the href attribute
        const linkPath = new URL(link.href, window.location.origin).pathname;
        
        // Set active class if the link path matches the current path
        // or if we're at the root and the link is to the dashboard
        if (linkPath === currentPath || (currentPath === '/' && linkPath === '/')) {
            link.classList.add('active');
        }
    });
}

/**
 * Initialize Bootstrap tooltips
 */
function initTooltips() {
    // Initialize all tooltips
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    const tooltipList = [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));
}

/**
 * Initialize Bootstrap toasts
 */
function initToasts() {
    // Initialize all toasts
    const toastElList = document.querySelectorAll('.toast');
    const toastList = [...toastElList].map(toastEl => new bootstrap.Toast(toastEl));
}

/**
 * Handle form submissions
 */
function handleFormSubmissions() {
    // Find all forms with data-api-submit attribute
    const forms = document.querySelectorAll('form[data-api-submit]');
    
    forms.forEach(form => {
        form.addEventListener('submit', async function(event) {
            event.preventDefault();
            
            // Get form data
            const formData = new FormData(form);
            const formObject = {};
            formData.forEach((value, key) => {
                formObject[key] = value;
            });
            
            // Get API endpoint from data attribute
            const endpoint = form.getAttribute('data-api-submit');
            
            try {
                // Submit form data
                const response = await API.post(endpoint, formObject);
                
                // Show success message
                UI.showToast('success', 'Success', form.getAttribute('data-success-message') || 'Form submitted successfully');
                
                // Reset form if data-reset attribute is present
                if (form.hasAttribute('data-reset')) {
                    form.reset();
                }
                
                // Call success callback if specified
                const successCallback = form.getAttribute('data-success-callback');
                if (successCallback && typeof window[successCallback] === 'function') {
                    window[successCallback](response);
                }
                
                // Refresh dashboard if data-refresh-dashboard attribute is present
                if (form.hasAttribute('data-refresh-dashboard')) {
                    Dashboard.refresh();
                }
            } catch (error) {
                // Error is already handled by API utility
            }
        });
    });
}

// Export objects for use in other scripts
window.API = API;
window.UI = UI;
window.ErrorHandler = ErrorHandler;
window.Dashboard = Dashboard;

/**
 * Last Oasis Manager Web Interface
 * Main JavaScript functionality
 */

// Configuration
const config = {
    refreshInterval: 30000, // 30 seconds refresh interval
    apiBaseUrl: '/api',     // Base URL for API endpoints
    maxRetries: 3,          // Maximum number of retries for failed API calls
    toastDuration: 5000     // Duration of toast notifications in ms
};

// Global state
const state = {
    servers: [],
    mods: [],
    lastUpdate: null,
    refreshTimer: null,
    currentPage: document.location.pathname,
    apiCallsInProgress: 0
};

// Utility functions
const utils = {
    /**
     * Format a timestamp for display
     */
    formatTimestamp: function(timestamp) {
        if (!timestamp) return 'N/A';
        
        // If it's a date string, convert to date object
        if (typeof timestamp === 'string') {
            return new Date(timestamp).toLocaleString();
        }
        
        return timestamp.toLocaleString();
    },
    
    /**
     * Show a toast notification
     */
    showToast: function(message, type = 'info') {
        // Create toast container if it doesn't exist
        let toastContainer = document.getElementById('toast-container');
        if (!toastContainer) {
            toastContainer = document.createElement('div');
            toastContainer.id = 'toast-container';
            toastContainer.className = 'position-fixed bottom-0 end-0 p-3';
            document.body.appendChild(toastContainer);
        }
        
        // Generate random ID for this toast
        const toastId = 'toast-' + Math.random().toString(36).substr(2, 9);
        
        // Create toast element
        const toast = document.createElement('div');
        toast.className = `toast align-items-center text-white bg-${type} border-0`;
        toast.setAttribute('role', 'alert');
        toast.setAttribute('aria-live', 'assertive');
        toast.setAttribute('aria-atomic', 'true');
        toast.id = toastId;
        
        // Toast content
        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">
                    <i class="fas fa-${type === 'info' ? 'info-circle' : (type === 'success' ? 'check-circle' : 'exclamation-circle')} me-2"></i>
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        `;
        
        // Add to container
        toastContainer.appendChild(toast);
        
        // Initialize and show toast
        const bsToast = new bootstrap.Toast(toast, {
            autohide: true,
            delay: config.toastDuration
        });
        
        bsToast.show();
        
        // Remove after hiding
        toast.addEventListener('hidden.bs.toast', function() {
            toast.remove();
        });
    },
    
    /**
     * Display an error message
     */
    showError: function(message, error = null) {
        console.error(message, error);
        this.showToast(message, 'danger');
    }
};

// API functions
const api = {
    /**
     * Make a request to the API
     */
    request: async function(endpoint, options = {}) {
        const url = `${config.apiBaseUrl}${endpoint}`;
        state.apiCallsInProgress++;
        
        try {
            // Update UI to show loading state
            this.updateLoadingState(true);
            
            const response = await fetch(url, options);
            
            if (!response.ok) {
                // Handle non-200 responses
                const errorText = await response.text();
                throw new Error(`API error (${response.status}): ${errorText}`);
            }
            
            return await response.json();
        } catch (error) {
            utils.showError(`API request failed: ${error.message}`, error);
            throw error;
        } finally {
            state.apiCallsInProgress--;
            this.updateLoadingState(false);
        }
    },
    
    /**
     * Update UI elements to reflect loading state
     */
    updateLoadingState: function(isLoading) {
        const spinners = document.querySelectorAll('.api-loading-indicator');
        const method = isLoading ? 'add' : 'remove';
        
        spinners.forEach(spinner => {
            spinner.classList[method]('d-inline-block');
            spinner.classList[method === 'add' ? 'remove' : 'add']('d-none');
        });
        
        // If we have a refresh button, update its state
        const refreshBtn = document.getElementById('refresh-btn');
        if (refreshBtn) {
            refreshBtn.disabled = isLoading;
            
            // If it contains an icon, add spin animation
            const icon = refreshBtn.querySelector('i');
            if (icon) {
                icon.classList[isLoading ? 'add' : 'remove']('fa-spin');
            }
        }
    },
    
    /**
     * Get all servers
     */
    getServers: async function() {
        try {
            const data = await this.request('/servers');
            state.servers = data;
            return data;
        } catch (error) {
            utils.showError('Failed to load server data');
            return [];
        }
    },
    
    /**
     * Perform an action on a server
     */
    serverAction: async function(serverId, action) {
        try {
            return await this.request('/servers/action', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    server_id: serverId,
                    action: action
                })
            });
        } catch (error) {
            utils.showError(`Failed to ${action} server ${serverId}`);
            throw error;
        }
    },
    
    /**
     * Get all mods
     */
    getMods: async function() {
        try {
            const data = await this.request('/mods');
            state.mods = data;
            return data;
        } catch (error) {
            utils.showError('Failed to load mod data');
            return [];
        }
    },
    
    /**
     * Send an admin message
     */
    sendAdminMessage: async function(message, serverIds = []) {
        try {
            return await this.request('/admin/message', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message: message,
                    server_ids: serverIds
                })
            });
        } catch (error) {
            utils.showError('Failed to send admin message');
            throw error;
        }
    },
    
    /**
     * Get logs for a server
     */
    getLogs: async function(serverId, lines = 100) {
        try {
            return await this.request(`/logs/${serverId}?lines=${lines}`);
        } catch (error) {
            utils.showError(`Failed to load logs for server ${serverId}`);
            return { logs: [] };
        }
    },
    
    /**
     * Get dashboard summary data
     */
    getDashboard: async function() {
        try {
            // Simplified dashboard data - in a real implementation, this would call a dedicated API endpoint
            const [servers, mods] = await Promise.all([
                this.getServers(),
                this.getMods()
            ]);
            
            return {
                servers,
                mods,
                system: {
                    serverUpdateStatus: 'Up to date',
                    modUpdateStatus: 'Up to date',
                    apiStatus: 'Online',
                    lastCheck: new Date()
                }
            };
        } catch (error) {
            utils.showError('Failed to load dashboard data');
            return {
                servers: [],
                mods: [],
                system: {
                    serverUpdateStatus: 'Unknown',
                    modUpdateStatus: 'Unknown',
                    apiStatus: 'Error',
                    lastCheck: new Date()
                }
            };
        }
    }
};

// UI update functions
const ui = {
    /**
     * Update server status display
     */
    updateServerStatus: function(servers) {
        const container = document.getElementById('server-status-container');
        if (!container) return;
        
        let html = '';
        servers.forEach(server => {
            html += `
                <div class="server-card mb-3">
                    <div class="d-flex align-items-center">
                        <div class="status-indicator ${server.status === 'online' ? 'bg-success' : 'bg-danger'} me-3"></div>
                        <div class="flex-grow-1">
                            <h5 class="mb-0">${server.tile_name || server.server_id}</h5>
                            <small class="text-muted">${server.server_id}</small>
                        </div>
                        <div class="server-actions">
                            ${server.status === 'online' ? `
                                <button class="btn btn-sm btn-warning me-1 server-action" data-server-id="${server.server_id}" data-action="restart">
                                    <i class="fas fa-sync-alt"></i>
                                </button>
                                <button class="btn btn-sm btn-danger server-action" data-server-id="${server.server_id}" data-action="stop">
                                    <i class="fas fa-stop"></i>
                                </button>
                            ` : `
                                <button class="btn btn-sm btn-success server-action" data-server-id="${server.server_id}" data-action="start">
                                    <i class="fas fa-play"></i>
                                </button>
                            `}
                        </div>
                    </div>
                </div>
            `;
        });
        
        container.innerHTML = html;
        
        // Reattach event listeners
        this.attachServerActionHandlers();
    },
    
    /**
     * Update mod status display
     */
    updateModStatus: function(mods) {
        const container = document.getElementById('mods-table-body');
        if (!container) return;
        
        let html = '';
        mods.forEach(mod => {
            html += `
                <tr>
                    <td>${mod.name}</td>
                    <td>${mod.version}</td>
                    <td>${mod.last_update}</td>
                    <td>
                        <span class="badge bg-success">${mod.status}</span>
                    </td>
                </tr>
            `;
        });
        
        container.innerHTML = html;
    },
    
    /**
     * Update system status display
     */
    updateSystemStatus: function(system) {
        const serverUpdateStatus = document.getElementById('server-update-status');
        const modUpdateStatus = document.getElementById('mod-update-status');
        const apiStatus = document.getElementById('api-status');
        const lastCheckTime = document.getElementById('last-check-time');
        
        if (serverUpdateStatus) {
            serverUpdateStatus.textContent = system.serverUpdateStatus;
            serverUpdateStatus.className = `badge ${system.serverUpdateStatus === 'Up to date' ? 'bg-success' : 'bg-warning'}`;
        }
        
        if (modUpdateStatus) {
            modUpdateStatus.textContent = system.modUpdateStatus;
            modUpdateStatus.className = `badge ${system.modUpdateStatus === 'Up to date' ? 'bg-success' : 'bg-warning'}`;
        }
        
        if (apiStatus) {
            apiStatus.textContent = system.apiStatus;
            apiStatus.className = `badge ${system.apiStatus === 'Online' ? 'bg-success' : 'bg-danger'}`;
        }
        
        if (lastCheckTime) {
            lastCheckTime.textContent = utils.formatTimestamp(system.lastCheck);
        }
    },
    
    /**
     * Attach event handlers for server action buttons
     */
    attachServerActionHandlers: function() {
        document.querySelectorAll('.server-action').forEach(button => {
            button.addEventListener('click', async function() {
                const serverId = this.dataset.serverId;
                const action = this.dataset.action;
                
                try {
                    // Disable the button while action is in progress
                    this.disabled = true;
                    
                    // Perform the action
                    await api.serverAction(serverId, action);
                    
                    // Show success message
                    utils.showToast(
                        `${action.charAt(0).toUpperCase() + action.slice(1)} command sent to ${serverId}`,
                        'success'
                    );
                    
                    // Refresh data after a delay
                    setTimeout(() => {
                        refreshData();
                    }, 2000);
                } catch (error) {
                    // Error is already handled by the API function
                } finally {
                    this.disabled = false;
                }
            });
        });
    },
    
    /**
     * Attach event handler for admin message form
     */
    attachAdminMessageHandler: function() {
        const form = document.getElementById('admin-message-form');
        if (!form) return;
        
        form.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const messageInput = document.getElementById('admin-message');
            const message = messageInput.value.trim();
            
            if (!message) return;
            
            try {
                const submitButton = form.querySelector('button[type="submit"]');
                submitButton.disabled = true;
                
                await api.sendAdminMessage(message);
                
                // Clear form and show success message
                messageInput.value = '';
                utils.showToast('Message sent to all servers', 'success');
            } catch (error) {
                // Error is already handled by the API function
            } finally {
                form.querySelector('button[type="submit"]').disabled = false;
            }
        });
    },
    
    /**
     * Attach event handlers for quick action buttons
     */
    attachQuickActionHandlers: function() {
        // Start all servers
        const startAllBtn = document.getElementById('start-all-servers-btn');
        if (startAllBtn) {
            startAllBtn.addEventListener('click', async function() {
                this.disabled = true;
                
                try {
                    // Get all offline servers
                    const offlineServers = state.servers.filter(server => server.status !== 'online');
                    
                    if (offlineServers.length === 0) {
                        utils.showToast('All servers are already online', 'info');
                        return;
                    }
                    
                    // Start each offline server
                    for (const server of offlineServers) {
                        await api.serverAction(server.server_id, 'start');
                    }
                    
                    utils.showToast(`Starting ${offlineServers.length} servers`, 'success');
                    
                    // Refresh after a delay
                    setTimeout(() => {
                        refreshData();
                    }, 2000);
                } catch (error) {
                    // Error is already handled by the API function
                } finally {
                    this.disabled = false;
                }
            });
        }
        
        // Stop all servers
        const stopAllBtn = document.getElementById('stop-all-servers-btn');
        if (stopAllBtn) {
            stopAllBtn.addEventListener('click', async function() {
                if (!confirm('Are you sure you want to stop all servers?')) {
                    return;
                }
                
                this.disabled = true;
                
                try {
                    // Get all online servers
                    const onlineServers = state.servers.filter(server => server.status === 'online');
                    
                    if (onlineServers.length === 0) {
                        utils.showToast('No servers are currently online', 'info');
                        return;
                    }
                    
                    // Stop each online server
                    for (const server of onlineServers) {
                        await api.serverAction(server.server_id, 'stop');
                    }
                    
                    utils.showToast(`Stopping ${onlineServers.length} servers`, 'success');
                    
                    // Refresh after a delay
                    setTimeout(() => {
                        refreshData();
                    }, 2000);
                } catch (error) {
                    // Error is already handled by the API function
                } finally {
                    this.disabled = false;
                }
            });
        }
        
        // Check for updates
        const checkUpdatesBtn = document.getElementById('check-updates-btn');
        if (checkUpdatesBtn) {
            checkUpdatesBtn.addEventListener('click', async function() {
                this.disabled = true;
                
                try {
                    const response = await api.request('/mods/check');
                    
                    if (response.updates_available) {
                        utils.showToast('Updates available for some mods!', 'warning');
                    } else {
                        utils.showToast('All mods are up to date', 'success');
                    }
                    
                    // Refresh data
                    refreshData();
                } catch (error) {
                    // Error is already handled by the API function
                } finally {
                    this.disabled = false;
                }
            });
        }
        
        // Update mods
        const updateModsBtn = document.getElementById('update-mods-btn');
        if (updateModsBtn) {
            updateModsBtn.addEventListener('click', async function() {
                if (!confirm('Are you sure you want to update all mods?')) {
                    return;
                }
                
                this.disabled = true;
                
                try {
                    const response = await api.request('/mods/update', {
                        method: 'POST'
                    });
                    
                    utils.showToast(response.message || 'Mods updated successfully', 'success');
                    
                    // Refresh after a delay
                    setTimeout(() => {
                        refreshData();
                    }, 2000);
                } catch (error) {
                    // Error is already handled by the API function
                } finally {
                    this.disabled = false;
                }
            });
        }
    }
};

/**
 * Refresh all data on the current page
 */
function refreshData() {
    // Update the last refresh time
    state.lastUpdate = new Date();
    
    const refreshTimeElement = document.getElementById('last-update-time');
    if (refreshTimeElement) {
        refreshTimeElement.textContent = utils.formatTimestamp(state.lastUpdate);
    }
    
    // Determine what data to refresh based on the current page
    switch (state.currentPage) {
        case '/':
            refreshDashboard();
            break;
        case '/servers':
            refreshServers();
            break;
        case '/mods':
            refreshMods();
            break;
        case '/logs':
            // Logs are typically refreshed manually or when a specific server is selected
            break;
        case '/config':
            // Configuration doesn't need regular refreshing
            break;
        default:
            // Default to dashboard refresh
            refreshDashboard();
    }
}

/**
 * Refresh dashboard data
 */
async function refreshDashboard() {
    try {
        const data = await api.getDashboard();
        
        // Update UI components
        ui.updateServerStatus(data.servers);
        ui.updateModStatus(data.mods);
        ui.updateSystemStatus(data.system);
    } catch (error) {
        // Error is already handled by the API function
    }
}

/**
 * Refresh servers data
 */
async function refreshServers() {
    try {
        const servers = await api.getServers();
        ui.updateServerStatus(servers);
    } catch (error) {
        // Error is already handled by the API function
    }
}

/**
 * Refresh mods data
 */
async function refreshMods() {
    try {
        const mods = await api.getMods();
        ui.updateModStatus(mods);
    } catch (error) {
        // Error is already handled by the API function
    }
}

/**
 * Setup auto-refresh
 */
function setupAutoRefresh() {
    // Clear any existing refresh interval
    if (state.refreshTimer) {
        clearInterval(state.refreshTimer);
    }
    
    // Set up new refresh interval
    state.refreshTimer = setInterval(() => {
        refreshData();
    }, config.refreshInterval);
    
    // Do an initial refresh
    refreshData();
}

/**
 * Initialize the page
 */
function initPage() {
    // Set the current page in state
    state.currentPage = window.location.pathname;
    
    // Attach handlers for navigation
    const navLinks = document.querySelectorAll('.navbar-nav .nav-link');
    navLinks.forEach(link => {
        // Remove any existing active classes
        link.classList.remove('active');
        
        // Set active class for current page
        if (link.getAttribute('href') === state.currentPage) {
            link.classList.add('active');
        }
    });
    
    // Initialize components based on the current page
    ui.attachQuickActionHandlers();
    ui.attachAdminMessageHandler();
    
    // Refresh button handler
    const refreshBtn = document.getElementById('refresh-btn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', function() {
            refreshData();
        });
    }
    
    // Setup auto-refresh
    setupAutoRefresh();
    
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl)
    });
    
    // Initialize popovers
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl)
    });
}

// Initialize when the DOM is fully loaded
document.addEventListener('DOMContentLoaded', function() {
    initPage();
});

// If the window is resized, update any UI elements that need it
window.addEventListener('resize', function() {
    // Responsive adjustments if needed
});

// Handle page visibility changes (tab switching, etc.)
document.addEventListener('visibilitychange', function() {
    if (document.visibilityState === 'visible') {
        // Refresh data when tab becomes visible again
        refreshData();
    }
});
