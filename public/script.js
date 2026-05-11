'use strict';

const form       = document.getElementById('pipeline-form');
const submitBtn  = document.getElementById('submit-btn');
const clearBtn   = document.getElementById('clear-btn');
const statusBox  = document.getElementById('form-status');

const fields = {
  role:        document.getElementById('target-role'),
  location:    document.getElementById('target-location'),
  greenhouse:  document.getElementById('greenhouse-companies'),
  lever:       document.getElementById('lever-companies'),
};

const errors = {
  role:       document.getElementById('error-role'),
  location:   document.getElementById('error-location'),
  greenhouse: document.getElementById('error-greenhouse'),
  lever:      document.getElementById('error-lever'),
};

// ── Validation ────────────────────────────────────────────────────────────────

const SLUG_RE = /^[a-z0-9]([a-z0-9-]*[a-z0-9])?(,[a-z0-9]([a-z0-9-]*[a-z0-9])?)*$/i;

function validateSlugs(value) {
  if (!value.trim()) return true;          // optional fields
  return SLUG_RE.test(value.trim());
}

function clearFieldError(key) {
  errors[key].textContent = '';
  fields[key].removeAttribute('aria-invalid');
}

function setFieldError(key, msg) {
  errors[key].textContent = msg;
  fields[key].setAttribute('aria-invalid', 'true');
  fields[key].focus();
}

function validate() {
  let ok = true;

  ['role', 'location'].forEach(k => clearFieldError(k));
  ['greenhouse', 'lever'].forEach(k => clearFieldError(k));

  if (!fields.role.value.trim()) {
    setFieldError('role', 'Target Role is required.');
    ok = false;
  }

  if (!fields.location.value.trim()) {
    setFieldError('location', 'Location is required.');
    ok = false;
  }

  if (!validateSlugs(fields.greenhouse.value)) {
    setFieldError('greenhouse', 'Use lowercase slugs separated by commas (e.g. stripe,airbnb).');
    ok = false;
  }

  if (!validateSlugs(fields.lever.value)) {
    setFieldError('lever', 'Use lowercase slugs separated by commas (e.g. jumpcloud,plaid).');
    ok = false;
  }

  return ok;
}

// ── UI state helpers ──────────────────────────────────────────────────────────

function showStatus(msg, type) {
  statusBox.textContent   = msg;
  statusBox.className     = `status-message ${type}`;
  statusBox.hidden        = false;
}

function hideStatus() {
  statusBox.hidden    = true;
  statusBox.className = 'status-message';
}

function setLoading(loading) {
  const text    = submitBtn.querySelector('.btn-text');
  const spinner = submitBtn.querySelector('.btn-spinner');
  submitBtn.disabled = loading;
  text.textContent   = loading ? 'Starting pipeline…' : 'Run Pipeline';
  spinner.hidden     = !loading;
}

// ── Submit ────────────────────────────────────────────────────────────────────

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  hideStatus();

  if (!validate()) return;

  setLoading(true);
  showStatus('Sending request to GitHub Actions…', 'loading');

  const payload = {
    target_role:           fields.role.value.trim(),
    target_location:       fields.location.value.trim(),
    greenhouse_companies:  fields.greenhouse.value.trim(),
    lever_companies:       fields.lever.value.trim(),
  };

  try {
    const res = await fetch('/.netlify/functions/trigger', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(payload),
    });

    const data = await res.json().catch(() => ({}));

    if (res.ok) {
      showStatus(
        '✅ Pipeline started! Results will appear in the Google Sheet in 3–5 minutes.',
        'success'
      );
    } else {
      const msg = data.error || `Server error (${res.status}). Please try again.`;
      showStatus(`❌ ${msg}`, 'error');
    }
  } catch {
    showStatus('❌ Network error — check your connection and try again.', 'error');
  } finally {
    setLoading(false);
  }
});

// ── Clear ─────────────────────────────────────────────────────────────────────

clearBtn.addEventListener('click', () => {
  form.reset();
  Object.keys(errors).forEach(clearFieldError);
  hideStatus();
  fields.role.focus();
});

// ── Inline validation on blur ─────────────────────────────────────────────────

fields.role.addEventListener('blur', () => {
  clearFieldError('role');
  if (!fields.role.value.trim()) setFieldError('role', 'Target Role is required.');
});

fields.location.addEventListener('blur', () => {
  clearFieldError('location');
  if (!fields.location.value.trim()) setFieldError('location', 'Location is required.');
});

fields.greenhouse.addEventListener('blur', () => {
  clearFieldError('greenhouse');
  if (!validateSlugs(fields.greenhouse.value)) {
    setFieldError('greenhouse', 'Use lowercase slugs separated by commas (e.g. stripe,airbnb).');
  }
});

fields.lever.addEventListener('blur', () => {
  clearFieldError('lever');
  if (!validateSlugs(fields.lever.value)) {
    setFieldError('lever', 'Use lowercase slugs separated by commas (e.g. jumpcloud,plaid).');
  }
});
