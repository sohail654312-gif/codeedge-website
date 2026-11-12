(() => {
  'use strict';

  const form = document.querySelector('[data-enquiry]');
  if (!form) return;

  const steps = Array.from(form.querySelectorAll('.form-step'));
  const progress = Array.from(form.querySelectorAll('.progress i'));
  const preview = form.querySelector('[data-preview]');
  const previewMessage = preview.querySelector('[data-message]');
  const whatsappLink = preview.querySelector('[data-whatsapp-request]');
  const packageField = form.elements.namedItem('package');
  const requestedPackage = new URLSearchParams(location.search).get('package');
  if (Array.from(packageField.options).some(option => option.value === requestedPackage)) {
    packageField.value = requestedPackage;
  }

  let currentStep = 0;

  function showStep(index) {
    currentStep = index;
    steps.forEach((step, position) => {
      step.classList.toggle('active', position === index);
      progress[position].classList.toggle('on', position <= index);
    });
    steps[index].querySelector('h2').focus();
  }

  function validateStep(index) {
    const invalid = steps[index].querySelector(':invalid');
    if (!invalid) return true;
    if (currentStep !== index) showStep(index);
    invalid.reportValidity();
    return false;
  }

  function clearPreview() {
    preview.hidden = true;
    previewMessage.textContent = '';
    whatsappLink.removeAttribute('href');
  }

  form.querySelectorAll('[data-next]').forEach(button => {
    button.addEventListener('click', () => {
      if (validateStep(currentStep)) showStep(currentStep + 1);
    });
  });

  form.querySelectorAll('[data-back]').forEach(button => {
    button.addEventListener('click', () => {
      clearPreview();
      showStep(currentStep - 1);
    });
  });

  form.addEventListener('input', clearPreview);
  form.addEventListener('submit', event => {
    event.preventDefault();
    if (!validateStep(currentStep)) return;
    if (currentStep < steps.length - 1) {
      showStep(currentStep + 1);
      return;
    }
    if (!steps.every((_, index) => validateStep(index))) return;

    const fields = new FormData(form);
    const details = [
      ['Name', 'name'],
      ['Business', 'business'],
      ['Email', 'email'],
      ['Phone', 'phone'],
      ['Business type', 'type'],
      ['Current setup', 'setup'],
      ['Main priority', 'priority'],
      ['Budget', 'budget'],
      ['Start timeframe', 'timeframe'],
    ];
    const lines = ['Hello Codeedge, I’d like to discuss my business.', ''];
    if (packageField.value) lines.push('Package of interest: ' + packageField.selectedOptions[0].textContent);
    for (const [label, name] of details) {
      const value = fields.get(name).trim();
      if (value) lines.push(label + ': ' + value);
    }
    const message = lines.join('\n');
    previewMessage.textContent = message;
    const url = new URL(whatsappLink.dataset.whatsappRequest);
    url.searchParams.set('text', message);
    whatsappLink.href = url.href;
    preview.hidden = false;
    preview.querySelector('h3').focus();
    form.dispatchEvent(new Event('codeedge:request-prepared'));
  });

  form.noValidate = true;
  form.hidden = false;
})();
