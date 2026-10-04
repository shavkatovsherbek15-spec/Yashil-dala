// Kichik progressiv yaxshilanishlar: sahifalar JS'siz ham ishlaydi.
(function () {
  'use strict';

  // Bosh sahifa: ekin tanlanganda muammolar ro'yxatini to'ldirish
  document.querySelectorAll('[data-picker]').forEach(function (form) {
    var map = JSON.parse(form.dataset.problems || '{}');
    var select = form.querySelector('select[name="problem"]');
    var placeholder = select.options[0].textContent;
    form.addEventListener('change', function (e) {
      if (e.target.name !== 'crop') return;
      var list = map[e.target.value] || [];
      select.innerHTML = '';
      list.forEach(function (p) {
        var opt = document.createElement('option');
        opt.value = p.slug;
        opt.textContent = p.name;
        select.appendChild(opt);
      });
      select.disabled = list.length === 0;
      if (!list.length) {
        var empty = document.createElement('option');
        empty.value = '';
        empty.textContent = placeholder;
        select.appendChild(empty);
      }
    });
  });

  // Soni: − / + tugmalari
  document.querySelectorAll('[data-qty]').forEach(function (box) {
    var input = box.querySelector('input');
    box.addEventListener('click', function (e) {
      var btn = e.target.closest('[data-step]');
      if (!btn) return;
      var min = +input.min || 1;
      var max = +input.max || 99;
      var next = (parseInt(input.value, 10) || min) + +btn.dataset.step;
      input.value = Math.min(max, Math.max(min, next));
    });
  });

  // Mahsulot: qadoq tanlanganda narxni yangilash
  document.querySelectorAll('[data-buy]').forEach(function (form) {
    var priceOut = form.querySelector('[data-price-out]');
    var packOut = form.querySelector('[data-pack-out]');
    form.addEventListener('change', function (e) {
      if (e.target.name !== 'variant_id') return;
      priceOut.textContent = e.target.dataset.price;
      packOut.textContent = e.target.dataset.pack;
    });
  });

  // Katalog: filtr o'zgarganda formani yuborish
  document.querySelectorAll('[data-autosubmit]').forEach(function (form) {
    form.addEventListener('change', function (e) {
      if (e.target.tagName === 'SELECT') form.submit();
    });
  });

  // Telefon: 90 123 45 67 ko'rinishida formatlash
  document.querySelectorAll('[data-phone]').forEach(function (input) {
    input.addEventListener('input', function () {
      var d = input.value.replace(/\D/g, '');
      if (d.length > 9 && d.indexOf('998') === 0) d = d.slice(3);
      d = d.slice(0, 9);
      var parts = [d.slice(0, 2), d.slice(2, 5), d.slice(5, 7), d.slice(7, 9)].filter(Boolean);
      input.value = parts.join(' ');
    });
  });
})();
