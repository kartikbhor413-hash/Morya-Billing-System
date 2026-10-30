/**
 * MORAYA ELECTRIC - BILLING & CALCULATIONS ENGINE
 * Decimal-safe client calculations + autocomplete + drafts + invoice submission
 */

(function () {
  const itemsBody = document.getElementById('itemsBody');
  const btnAddBlankRow = document.getElementById('btnAddBlankRow');
  const btnGenerateInvoice = document.getElementById('btnGenerateInvoice');
  const btnSaveDraft = document.getElementById('btnSaveDraft');
  const btnResetForm = document.getElementById('btnResetForm');

  // Customer Autocomplete elements
  const custSearchInput = document.getElementById('customerSearchInput');
  const custResults = document.getElementById('customerResults');
  const customerId = document.getElementById('customerId');
  const customerName = document.getElementById('customerName');
  const customerMobile = document.getElementById('customerMobile');
  const customerAddress = document.getElementById('customerAddress');

  // Service Autocomplete elements
  const serviceSearchInput = document.getElementById('serviceSearchInput');
  const serviceResults = document.getElementById('serviceResults');

  // Live Summary Elements
  const liveSubtotal = document.getElementById('liveSubtotal');
  const discountAmount = document.getElementById('discountAmount');
  const taxPercent = document.getElementById('taxPercent');
  const liveNetAmount = document.getElementById('liveNetAmount');
  const liveNetMirror = document.getElementById('liveNetMirror');
  const liveAdvanceMirror = document.getElementById('liveAdvanceMirror');
  const cashAdvance = document.getElementById('cashAdvance');
  const upiAdvance = document.getElementById('upiAdvance');
  const bankAdvance = document.getElementById('bankAdvance');
  const liveTotalAdvance = document.getElementById('liveTotalAdvance');
  const liveBalanceDue = document.getElementById('liveBalanceDue');
  const liveStatusBadge = document.getElementById('liveStatusBadge');
  const liveWords = document.getElementById('liveWords');

  // Indian Number to Words (Client-side live display)
  const ones = ['', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine', 'Ten',
                'Eleven', 'Twelve', 'Thirteen', 'Fourteen', 'Fifteen', 'Sixteen', 'Seventeen', 'Eighteen', 'Nineteen'];
  const tens = ['', '', 'Twenty', 'Thirty', 'Forty', 'Fifty', 'Sixty', 'Seventy', 'Eighty', 'Ninety'];

  function twoDigits(n) {
    if (n < 20) return ones[n];
    const rem = n % 10;
    return tens[Math.floor(n / 10)] + (rem ? ' ' + ones[rem] : '');
  }

  function threeDigits(n) {
    let s = '';
    const h = Math.floor(n / 100);
    const rem = n % 100;
    if (h) s += ones[h] + ' Hundred';
    if (rem) s += (h ? ' ' : '') + twoDigits(rem);
    return s;
  }

  function numberToWords(val) {
    const num = parseFloat(val) || 0;
    if (num === 0) return 'Zero Rupees Only';

    let rupees = Math.floor(num);
    const paise = Math.round((num - rupees) * 100);
    const parts = [];

    const crores = Math.floor(rupees / 10000000);
    rupees %= 10000000;
    if (crores) parts.push(twoDigits(crores) + ' Crore');

    const lakhs = Math.floor(rupees / 100000);
    rupees %= 100000;
    if (lakhs) parts.push(twoDigits(lakhs) + ' Lakh');

    const thousands = Math.floor(rupees / 1000);
    rupees %= 1000;
    if (thousands) parts.push(twoDigits(thousands) + ' Thousand');

    if (rupees) parts.push(threeDigits(rupees));

    let res = parts.length ? 'Rupees ' + parts.join(' ') : '';
    if (paise > 0) {
      const paiseStr = twoDigits(paise) + ' Paise';
      res += (res ? ' and ' : '') + paiseStr;
    }
    return res + ' Only';
  }

  function fmt(val) {
    return '₹' + (parseFloat(val) || 0).toLocaleString('en-IN', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    });
  }

  // -------------------------------------------------------------------------
  // Automatic Mathematical Calculations
  // -------------------------------------------------------------------------
  function recalculate() {
    let subtotal = 0;
    const rows = itemsBody.querySelectorAll('tr');

    rows.forEach((row, idx) => {
      const srCell = row.querySelector('.sr-num');
      if (srCell) srCell.textContent = idx + 1;

      const qtyInput = row.querySelector('.item-qty');
      const rateInput = row.querySelector('.item-rate');
      const amountCell = row.querySelector('.item-amount');

      const qty = Math.max(0, parseFloat(qtyInput ? qtyInput.value : 1) || 0);
      const rate = Math.max(0, parseFloat(rateInput ? rateInput.value : 0) || 0);
      const lineAmt = Math.round(qty * rate * 100) / 100;

      if (amountCell) amountCell.textContent = fmt(lineAmt);
      subtotal += lineAmt;
    });

    // Discount
    let disc = Math.max(0, parseFloat(discountAmount.value) || 0);
    disc = Math.min(disc, subtotal);

    const taxable = Math.max(0, subtotal - disc);

    // Tax
    const taxPct = Math.max(0, parseFloat(taxPercent.value) || 0);
    const taxAmt = Math.round(taxable * (taxPct / 100) * 100) / 100;

    // Net Amount
    const net = Math.round((taxable + taxAmt) * 100) / 100;

    // Advances
    const cAdv = Math.max(0, parseFloat(cashAdvance.value) || 0);
    const uAdv = Math.max(0, parseFloat(upiAdvance.value) || 0);
    const bAdv = Math.max(0, parseFloat(bankAdvance.value) || 0);
    const totalAdv = Math.round((cAdv + uAdv + bAdv) * 100) / 100;

    // Balance
    const balance = Math.max(0, Math.round((net - totalAdv) * 100) / 100);

    // Update UI
    liveSubtotal.textContent = fmt(subtotal);
    liveNetAmount.textContent = fmt(net);
    liveNetMirror.textContent = fmt(net);
    liveAdvanceMirror.textContent = fmt(totalAdv);
    liveTotalAdvance.textContent = fmt(totalAdv);
    liveBalanceDue.textContent = fmt(balance);

    // Status Badge
    if (net > 0 && totalAdv >= net) {
      liveStatusBadge.textContent = 'Paid';
      liveStatusBadge.className = 'badge-status paid';
    } else if (totalAdv > 0) {
      liveStatusBadge.textContent = 'Partially Paid';
      liveStatusBadge.className = 'badge-status partially-paid';
    } else {
      liveStatusBadge.textContent = 'Unpaid';
      liveStatusBadge.className = 'badge-status unpaid';
    }

    liveWords.textContent = numberToWords(net);
  }

  // Row Management
  function createRow(desc = '', rate = 0, qty = 1) {
    const row = document.createElement('tr');
    row.innerHTML = `
      <td style="text-align:center;font-weight:700;" class="sr-num"></td>
      <td>
        <input type="text" class="item-desc" placeholder="Service description or material" value="${desc}" required>
      </td>
      <td>
        <input type="number" class="item-qty" value="${qty}" min="0.01" step="any" style="text-align:center;">
      </td>
      <td>
        <input type="number" class="item-rate" value="${rate}" min="0" step="any" placeholder="0.00" style="text-align:right;">
      </td>
      <td style="text-align:right;font-weight:700;" class="item-amount">₹0.00</td>
      <td style="text-align:center;">
        <button type="button" class="remove-btn" title="Remove line">✕</button>
      </td>
    `;
    itemsBody.appendChild(row);
    recalculate();
    return row;
  }

  if (btnAddBlankRow) {
    btnAddBlankRow.addEventListener('click', () => createRow());
  }

  itemsBody.addEventListener('click', (e) => {
    if (e.target.closest('.remove-btn')) {
      const rows = itemsBody.querySelectorAll('tr');
      if (rows.length > 1) {
        e.target.closest('tr').remove();
        recalculate();
      } else {
        // Clear first row instead of deleting last row
        const r = rows[0];
        r.querySelector('.item-desc').value = '';
        r.querySelector('.item-qty').value = '1';
        r.querySelector('.item-rate').value = '0.00';
        recalculate();
      }
    }
  });

  // Listen to input changes anywhere in form
  document.getElementById('billingForm').addEventListener('input', recalculate);

  // -------------------------------------------------------------------------
  // The 8 Default Electrical Services Quick Chips
  // -------------------------------------------------------------------------
  const quickChips = document.getElementById('quickServiceChips');
  if (quickChips) {
    quickChips.addEventListener('click', (e) => {
      const btn = e.target.closest('.service-chip-btn');
      if (!btn) return;
      const sName = btn.dataset.name;
      const sRate = parseFloat(btn.dataset.rate) || 0;

      // Check if an empty row exists, otherwise add row
      const rows = itemsBody.querySelectorAll('tr');
      let targetRow = null;
      for (const r of rows) {
        if (!r.querySelector('.item-desc').value.trim()) {
          targetRow = r;
          break;
        }
      }

      if (targetRow) {
        targetRow.querySelector('.item-desc').value = sName;
        targetRow.querySelector('.item-rate').value = sRate;
        targetRow.querySelector('.item-qty').focus();
      } else {
        const nr = createRow(sName, sRate, 1);
        nr.querySelector('.item-qty').focus();
      }
      recalculate();
    });
  }

  // -------------------------------------------------------------------------
  // Customer Autocomplete Search
  // -------------------------------------------------------------------------
  let custDebounce = null;
  if (custSearchInput) {
    custSearchInput.addEventListener('input', () => {
      clearTimeout(custDebounce);
      const query = custSearchInput.value.trim();
      if (!query) {
        custResults.style.display = 'none';
        return;
      }
      custDebounce = setTimeout(async () => {
        try {
          const res = await fetch(`/api/customers?q=${encodeURIComponent(query)}`);
          const customers = await res.json();
          custResults.innerHTML = '';

          if (customers.length > 0) {
            customers.forEach((c) => {
              const div = document.createElement('div');
              div.className = 'autocomplete-item';
              div.innerHTML = `
                <div>
                  <strong>${c.name}</strong>
                  <div class="sub">📱 ${c.phone} ${c.address ? '• ' + c.address : ''}</div>
                </div>
              `;
              div.addEventListener('click', () => {
                customerId.value = c.id;
                customerName.value = c.name;
                customerMobile.value = c.phone;
                customerAddress.value = c.address || '';
                custResults.style.display = 'none';
                custSearchInput.value = '';
              });
              custResults.appendChild(div);
            });
          } else {
            const div = document.createElement('div');
            div.className = 'autocomplete-item add-new-option';
            div.textContent = `+ Add "${query}" as New Customer`;
            div.addEventListener('click', () => {
              document.getElementById('mCustName').value = query;
              document.getElementById('addCustomerModal').classList.add('active');
              custResults.style.display = 'none';
            });
            custResults.appendChild(div);
          }
          custResults.style.display = 'block';
        } catch (err) {
          console.error('Customer fetch error:', err);
        }
      }, 250);
    });

    document.addEventListener('click', (e) => {
      if (!custSearchInput.contains(e.target) && !custResults.contains(e.target)) {
        custResults.style.display = 'none';
      }
    });
  }

  // -------------------------------------------------------------------------
  // Smart Service Autocomplete Search
  // -------------------------------------------------------------------------
  let svcDebounce = null;
  if (serviceSearchInput) {
    serviceSearchInput.addEventListener('input', () => {
      clearTimeout(svcDebounce);
      const query = serviceSearchInput.value.trim();
      if (!query) {
        serviceResults.style.display = 'none';
        return;
      }
      svcDebounce = setTimeout(async () => {
        try {
          const res = await fetch(`/api/products?q=${encodeURIComponent(query)}`);
          const services = await res.json();
          serviceResults.innerHTML = '';

          if (services.length > 0) {
            services.forEach((s) => {
              const div = document.createElement('div');
              div.className = 'autocomplete-item';
              div.innerHTML = `
                <div>
                  <strong>${s.name}</strong>
                  <div class="sub">${s.category || 'Service'} • Unit: ${s.unit || 'Point'}</div>
                </div>
                <div style="font-weight:700;color:#0f172a;">${s.default_rate > 0 ? fmt(s.default_rate) : 'Rate on bill'}</div>
              `;
              div.addEventListener('click', () => {
                const rows = itemsBody.querySelectorAll('tr');
                let targetRow = null;
                for (const r of rows) {
                  if (!r.querySelector('.item-desc').value.trim()) {
                    targetRow = r;
                    break;
                  }
                }
                const rate = parseFloat(s.default_rate) || 0;
                if (targetRow) {
                  targetRow.querySelector('.item-desc').value = s.name;
                  targetRow.querySelector('.item-rate').value = rate;
                  targetRow.querySelector('.item-qty').focus();
                } else {
                  const nr = createRow(s.name, rate, 1);
                  nr.querySelector('.item-qty').focus();
                }
                serviceResults.style.display = 'none';
                serviceSearchInput.value = '';
                recalculate();
              });
              serviceResults.appendChild(div);
            });
          }

          // Always add "+ Add New Service" option
          const addOption = document.createElement('div');
          addOption.className = 'autocomplete-item add-new-option';
          addOption.textContent = `+ Add "${query}" as New Service`;
          addOption.addEventListener('click', () => {
            document.getElementById('mServiceName').value = query;
            document.getElementById('addServiceModal').classList.add('active');
            serviceResults.style.display = 'none';
          });
          serviceResults.appendChild(addOption);

          serviceResults.style.display = 'block';
        } catch (err) {
          console.error('Service fetch error:', err);
        }
      }, 200);
    });

    document.addEventListener('click', (e) => {
      if (!serviceSearchInput.contains(e.target) && !serviceResults.contains(e.target)) {
        serviceResults.style.display = 'none';
      }
    });
  }

  // -------------------------------------------------------------------------
  // Modals: Add Customer & Add Service
  // -------------------------------------------------------------------------
  document.getElementById('btnOpenAddCustomer').addEventListener('click', () => {
    document.getElementById('addCustomerModal').classList.add('active');
  });

  document.getElementById('btnSaveNewCustomer').addEventListener('click', async () => {
    const name = document.getElementById('mCustName').value.trim();
    const phone = document.getElementById('mCustPhone').value.trim();
    const address = document.getElementById('mCustAddress').value.trim();

    if (!name || !phone) {
      alert('Please enter both customer name and mobile number.');
      return;
    }

    try {
      const res = await fetch('/api/customers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, phone, address })
      });
      const data = await res.json();
      if (data.success) {
        customerId.value = data.id;
        customerName.value = name;
        customerMobile.value = phone;
        customerAddress.value = address;
        document.getElementById('addCustomerModal').classList.remove('active');
        showToast('Customer saved to database!', 'success');
      } else {
        alert(data.error || 'Failed to save customer.');
      }
    } catch (e) {
      alert('Error saving customer: ' + e.message);
    }
  });

  document.getElementById('btnOpenAddService').addEventListener('click', () => {
    document.getElementById('addServiceModal').classList.add('active');
  });

  document.getElementById('btnSaveNewService').addEventListener('click', async () => {
    const name = document.getElementById('mServiceName').value.trim();
    const rate = parseFloat(document.getElementById('mServiceRate').value) || 0;
    const unit = document.getElementById('mServiceUnit').value.trim() || 'Point';

    if (!name) {
      alert('Please enter service name.');
      return;
    }

    try {
      const res = await fetch('/api/products', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, default_rate: rate, unit, is_active: true })
      });
      const data = await res.json();
      if (data.success) {
        createRow(name, rate, 1);
        document.getElementById('addServiceModal').classList.remove('active');
        showToast('Service saved to catalog and added to bill!', 'success');
      } else {
        alert(data.error || 'Failed to save service.');
      }
    } catch (e) {
      alert('Error saving service: ' + e.message);
    }
  });

  // -------------------------------------------------------------------------
  // Save Draft (Separate from finalized invoices)
  // -------------------------------------------------------------------------
  btnSaveDraft.addEventListener('click', async () => {
    const items = [];
    itemsBody.querySelectorAll('tr').forEach((r) => {
      const desc = r.querySelector('.item-desc').value.trim();
      const qty = parseFloat(r.querySelector('.item-qty').value) || 1;
      const rate = parseFloat(r.querySelector('.item-rate').value) || 0;
      if (desc) items.push({ description: desc, quantity: qty, rate: rate });
    });

    const draftData = {
      customer_id: customerId.value,
      customer_name: customerName.value,
      customer_phone: customerMobile.value,
      customer_address: customerAddress.value,
      invoice_date: document.getElementById('invoiceDate').value,
      payment_type: document.getElementById('paymentType').value,
      items: items,
      discount_amount: parseFloat(discountAmount.value) || 0,
      tax_percent: parseFloat(taxPercent.value) || 0,
      cash_advance: parseFloat(cashAdvance.value) || 0,
      upi_advance: parseFloat(upiAdvance.value) || 0,
      bank_advance: parseFloat(bankAdvance.value) || 0
    };

    try {
      const res = await fetch('/api/draft', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(draftData)
      });
      const data = await res.json();
      if (data.success) {
        showToast('Draft saved successfully. (Not counted in sales/bills)', 'info');
      }
    } catch (e) {
      showToast('Could not save draft.', 'error');
    }
  });

  // -------------------------------------------------------------------------
  // Reset Form
  // -------------------------------------------------------------------------
  btnResetForm.addEventListener('click', () => {
    if (!confirm('Are you sure you want to reset the entire billing form?')) return;
    document.getElementById('billingForm').reset();
    customerId.value = '';
    itemsBody.innerHTML = '';
    createRow('', 0, 1);
    recalculate();
    showToast('Form reset.', 'info');
  });

  // -------------------------------------------------------------------------
  // Generate & Save Invoice (THE ONLY ACTION THAT CREATES A BILL)
  // -------------------------------------------------------------------------
  btnGenerateInvoice.addEventListener('click', async () => {
    const cName = customerName.value.trim();
    const cPhone = customerMobile.value.trim();

    if (!cName) {
      alert('Please enter Customer Name.');
      customerName.focus();
      return;
    }

    const items = [];
    let hasZeroRate = false;
    itemsBody.querySelectorAll('tr').forEach((r) => {
      const desc = r.querySelector('.item-desc').value.trim();
      const qty = parseFloat(r.querySelector('.item-qty').value) || 0;
      const rate = parseFloat(r.querySelector('.item-rate').value) || 0;
      if (desc) {
        if (rate <= 0) hasZeroRate = true;
        items.push({ description: desc, quantity: qty, rate: rate });
      }
    });

    if (items.length === 0) {
      alert('Please add at least one service or product item with description.');
      return;
    }

    if (hasZeroRate) {
      if (!confirm('One or more items have ₹0.00 rate. Do you wish to proceed?')) {
        return;
      }
    }

    const payload = {
      customer_id: customerId.value || null,
      customer_name: cName,
      customer_phone: cPhone,
      customer_address: customerAddress.value.trim(),
      invoice_number: document.getElementById('invoiceNumber').value.trim(),
      invoice_date: document.getElementById('invoiceDate').value,
      payment_type: document.getElementById('paymentType').value,
      items: items,
      discount_amount: parseFloat(discountAmount.value) || 0,
      discount_type: 'fixed',
      tax_percent: parseFloat(taxPercent.value) || 0,
      cash_advance: parseFloat(cashAdvance.value) || 0,
      upi_advance: parseFloat(upiAdvance.value) || 0,
      bank_advance: parseFloat(bankAdvance.value) || 0,
      notes: document.getElementById('customerNotes').value.trim()
    };

    // Prevent double submissions
    btnGenerateInvoice.disabled = true;
    const oldBtnHtml = btnGenerateInvoice.innerHTML;
    btnGenerateInvoice.innerHTML = `<span>Saving to Supabase Database...</span>`;

    try {
      const res = await fetch('/api/invoices/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();

      if (data.success && data.invoice_id) {
        showToast('Invoice generated and saved successfully!', 'success');
        // Redirect to invoice view
        window.location.href = `/invoices/${data.invoice_id}`;
      } else {
        alert(data.error || 'Failed to save invoice. Please check the fields and try again.');
        btnGenerateInvoice.disabled = false;
        btnGenerateInvoice.innerHTML = oldBtnHtml;
      }
    } catch (err) {
      alert('Network error while saving invoice: ' + err.message);
      btnGenerateInvoice.disabled = false;
      btnGenerateInvoice.innerHTML = oldBtnHtml;
    }
  });

  // Initial calculation
  recalculate();
})();
