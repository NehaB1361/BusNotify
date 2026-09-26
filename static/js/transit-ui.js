/**
 * BusNotify - Transit UI Component Utilities
 * Toasts, Status Badges, Live Polling Manager, and Skeleton Renderers
 */

const TransitUI = {
  /**
   * Generates accessible Transit Flow status badge with Icon + Label + Color (Section 7)
   */
  getStatusBadge(status) {
    const s = String(status || 'UNKNOWN').toUpperCase();
    let badgeClass = 'badge-inactive';
    let iconClass = 'bi-dash-circle';
    let label = s;

    switch (s) {
      case 'RUNNING':
      case 'AVAILABLE':
      case 'ON TIME':
        badgeClass = 'badge-ontime';
        iconClass = 'bi-check-circle-fill';
        label = 'ON TIME';
        break;
      case 'DELAYED':
        badgeClass = 'badge-delayed';
        iconClass = 'bi-exclamation-triangle-fill';
        label = 'DELAYED';
        break;
      case 'PUNCTURED':
        badgeClass = 'badge-punctured';
        iconClass = 'bi-wrench-adjustable-circle-fill';
        label = 'TYRE PUNCTURE';
        break;
      case 'BREAKDOWN':
      case 'CRITICAL':
        badgeClass = 'badge-critical';
        iconClass = 'bi-x-octagon-fill';
        label = 'BREAKDOWN';
        break;
      case 'DISPATCHED':
        badgeClass = 'badge-dispatched';
        iconClass = 'bi-arrow-right-circle-fill';
        label = 'DISPATCHED';
        break;
      case 'ASSIGNED':
        badgeClass = 'badge-assigned';
        iconClass = 'bi-person-check-fill';
        label = 'ASSIGNED';
        break;
      case 'ARRIVED':
        badgeClass = 'badge-ontime';
        iconClass = 'bi-geo-alt-fill';
        label = 'ARRIVED';
        break;
      case 'PASSENGER_TRANSFER':
        badgeClass = 'badge-dispatched';
        iconClass = 'bi-people-fill';
        label = 'TRANSFER IN PROGRESS';
        break;
      case 'RESOLVED':
      case 'COMPLETED':
        badgeClass = 'badge-ontime';
        iconClass = 'bi-check2-all';
        label = 'RESOLVED';
        break;
      case 'CANCELLED':
      case 'OFF_DUTY':
        badgeClass = 'badge-inactive';
        iconClass = 'bi-slash-circle-fill';
        label = 'CANCELLED';
        break;
    }

    return `<span class="tf-badge ${badgeClass}"><i class="bi ${iconClass}"></i> ${label}</span>`;
  },

  /**
   * Displays modern Bootstrap / Transit Flow toast
   */
  showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    if (!container) return;

    const toastEl = document.createElement('div');
    toastEl.className = `toast align-items-center text-white border-0 shadow-lg`;
    
    let bg = 'bg-primary';
    let icon = 'bi-info-circle-fill';
    if (type === 'success') { bg = 'bg-success'; icon = 'bi-check-circle-fill'; }
    else if (type === 'error' || type === 'danger') { bg = 'bg-danger'; icon = 'bi-exclamation-triangle-fill'; }
    else if (type === 'warning') { bg = 'bg-warning text-dark'; icon = 'bi-exclamation-circle-fill'; }

    toastEl.classList.add(bg);
    toastEl.setAttribute('role', 'alert');
    toastEl.setAttribute('aria-live', 'assertive');
    toastEl.setAttribute('aria-atomic', 'true');

    toastEl.innerHTML = `
      <div class="d-flex">
        <div class="toast-body d-flex align-items-center gap-2">
          <i class="bi ${icon}"></i>
          <span>${message}</span>
        </div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
      </div>
    `;

    container.appendChild(toastEl);
    const toast = new bootstrap.Toast(toastEl, { delay: 4000 });
    toast.show();

    toastEl.addEventListener('hidden.bs.toast', () => {
      toastEl.remove();
    });
  },

  /**
   * Start adaptive polling with automatic cleanup (Section 46)
   */
  startPolling(callback, intervalMs = 15000) {
    callback(); // execute once immediately
    return setInterval(() => {
      // Only poll when page is visible to conserve bandwidth
      if (!document.hidden) {
        callback();
      }
    }, intervalMs);
  },

  /**
   * Standard table loading row
   */
  renderLoadingRow(colspan = 6, message = 'Loading live data...') {
    return `
      <tr>
        <td colspan="${colspan}" class="text-center py-4 text-muted">
          <div class="d-inline-flex align-items-center gap-2">
            <span class="spinner-border spinner-border-sm text-primary" role="status" aria-hidden="true"></span>
            <span>${message}</span>
          </div>
        </td>
      </tr>
    `;
  },

  /**
   * Standard table empty state row
   */
  renderEmptyRow(colspan = 6, message = 'No records found.', icon = 'bi-inbox') {
    return `
      <tr>
        <td colspan="${colspan}" class="text-center py-4 text-muted">
          <div class="d-flex flex-column align-items-center justify-content-center py-2">
            <i class="bi ${icon} fs-3 text-secondary mb-1"></i>
            <span class="fw-medium">${message}</span>
          </div>
        </td>
      </tr>
    `;
  },

  /**
   * Standard table error state row
   */
  renderErrorRow(colspan = 6, message = 'Failed to load data. Please retry.') {
    return `
      <tr>
        <td colspan="${colspan}" class="text-center py-4 text-danger">
          <div class="d-flex flex-column align-items-center justify-content-center py-2">
            <i class="bi bi-exclamation-circle fs-3 text-danger mb-1"></i>
            <span class="fw-medium">${message}</span>
          </div>
        </td>
      </tr>
    `;
  }
};
