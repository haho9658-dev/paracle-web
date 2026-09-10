/* =========================================================
   Paracle Mobility — main.js
   ========================================================= */
(function () {
  'use strict';

  var prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ---------------------------------------------------------
     1. Header: scroll state, progress bar, back-to-top
     --------------------------------------------------------- */
  var header = document.getElementById('siteHeader');
  var progress = document.getElementById('scrollProgress');
  var toTop = document.getElementById('toTop');
  var ticking = false;

  function onScroll() {
    var y = window.scrollY || document.documentElement.scrollTop;
    var docH = document.documentElement.scrollHeight - window.innerHeight;

    header.classList.toggle('is-scrolled', y > 12);
    progress.style.width = (docH > 0 ? (y / docH) * 100 : 0) + '%';
    toTop.classList.toggle('is-visible', y > 600);

    highlightNav(y);
    ticking = false;
  }

  window.addEventListener('scroll', function () {
    if (!ticking) {
      window.requestAnimationFrame(onScroll);
      ticking = true;
    }
  }, { passive: true });

  toTop.addEventListener('click', function () {
    window.scrollTo({ top: 0, behavior: prefersReduced ? 'auto' : 'smooth' });
  });

  /* ---------------------------------------------------------
     2. Mobile navigation
     --------------------------------------------------------- */
  var nav = document.getElementById('nav');
  var navToggle = document.getElementById('navToggle');

  function setNav(open) {
    nav.classList.toggle('is-open', open);
    navToggle.classList.toggle('is-open', open);
    navToggle.setAttribute('aria-expanded', String(open));
    navToggle.setAttribute('aria-label', open ? '메뉴 닫기' : '메뉴 열기');
    // 메뉴가 열린 동안 뒤 본문이 함께 스크롤되지 않도록 잠근다
    document.body.classList.toggle('nav-open', open);
  }

  function closeNav() { setNav(false); }

  navToggle.addEventListener('click', function () {
    setNav(!nav.classList.contains('is-open'));
  });

  nav.addEventListener('click', function (e) {
    if (e.target.closest('a')) closeNav();
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') closeNav();
  });

  window.addEventListener('resize', function () {
    if (window.innerWidth > 860) closeNav();
  });

  /* ---------------------------------------------------------
     3. Active nav link on scroll
     --------------------------------------------------------- */
  var navLinks = Array.prototype.slice.call(document.querySelectorAll('.nav-link'));
  var sections = navLinks
    .map(function (a) { return document.querySelector(a.getAttribute('href')); })
    .filter(Boolean);

  function highlightNav(y) {
    var offset = y + (window.innerHeight * 0.32);
    var current = -1;
    for (var i = 0; i < sections.length; i++) {
      if (sections[i].offsetTop <= offset) current = i;
    }
    navLinks.forEach(function (link, i) {
      link.classList.toggle('is-active', i === current);
    });
  }

  /* ---------------------------------------------------------
     4. Scroll reveal
     --------------------------------------------------------- */
  var revealEls = document.querySelectorAll('.reveal');

  if (prefersReduced || !('IntersectionObserver' in window)) {
    revealEls.forEach(function (el) { el.classList.add('is-visible'); });
  } else {
    var revealObserver = new IntersectionObserver(function (entries, obs) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        var el = entry.target;
        var delay = parseInt(el.dataset.delay || '0', 10);
        setTimeout(function () { el.classList.add('is-visible'); }, delay);
        obs.unobserve(el);
      });
    }, { threshold: 0.14, rootMargin: '0px 0px -60px 0px' });

    revealEls.forEach(function (el) { revealObserver.observe(el); });
  }

  /* ---------------------------------------------------------
     5. Animated counters
     --------------------------------------------------------- */
  function formatNumber(value, decimals) {
    return decimals > 0
      ? value.toFixed(decimals)
      : Math.round(value).toLocaleString('ko-KR');
  }

  function runCounter(el) {
    var target = parseFloat(el.dataset.target);
    var decimals = parseInt(el.dataset.decimals || '0', 10);

    if (prefersReduced) {
      el.textContent = formatNumber(target, decimals);
      return;
    }

    var duration = 1500;
    var start = null;

    function step(ts) {
      if (start === null) start = ts;
      var p = Math.min((ts - start) / duration, 1);
      var eased = 1 - Math.pow(1 - p, 3);          // easeOutCubic
      el.textContent = formatNumber(target * eased, decimals);
      if (p < 1) window.requestAnimationFrame(step);
    }
    window.requestAnimationFrame(step);
  }

  var counters = document.querySelectorAll('.counter');
  if (!('IntersectionObserver' in window)) {
    counters.forEach(runCounter);
  } else {
    var counterObserver = new IntersectionObserver(function (entries, obs) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        runCounter(entry.target);
        obs.unobserve(entry.target);
      });
    }, { threshold: 0.5 });
    counters.forEach(function (el) { counterObserver.observe(el); });
  }

  /* ---------------------------------------------------------
     6. 가로 스크롤이 필요한 비교표에 스크롤 힌트 표시
     --------------------------------------------------------- */
  var tableScroll = document.querySelector('.table-scroll');
  var tableWrap = tableScroll && tableScroll.querySelector('.table-wrap');

  function updateTableHint() {
    if (!tableWrap) return;
    var overflow = tableWrap.scrollWidth - tableWrap.clientWidth;
    tableScroll.classList.toggle('is-scrollable', overflow > 4);
    tableScroll.classList.toggle('is-scrolled-end', tableWrap.scrollLeft >= overflow - 4);
  }

  if (tableWrap) {
    tableWrap.addEventListener('scroll', updateTableHint, { passive: true });
    window.addEventListener('resize', updateTableHint);
    window.addEventListener('load', updateTableHint);
    // 웹폰트가 적용되면 표 너비가 바뀐다
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(updateTableHint);
    updateTableHint();
  }

  /* ---------------------------------------------------------
     7. Caster lock mechanism demo
     --------------------------------------------------------- */
  var mechSvg = document.getElementById('mechSvg');
  var mechBtn = document.getElementById('mechBtn');
  var mechBtnLabel = document.getElementById('mechBtnLabel');
  var mechState = document.getElementById('mechState');
  var mechStateText = mechState.querySelector('.mech-state-text');
  var mechText = document.getElementById('mechText');
  var mechLeverLabel = document.getElementById('mechLeverLabel');

  var MECH_COPY = {
    free: {
      state: 'FREE — 평상시 자유 회전',
      lever: '레버 해제',
      button: '레버 당겨 잠그기',
      text: '평상시에는 캐스터가 자유롭게 회전해 좁은 실내에서도 기존과 똑같이 방향을 바꿀 수 있습니다. ' +
            '다만 문턱이나 틈을 만나면 바퀴가 옆으로 틀어져 끼거나 전복될 위험이 커집니다.'
    },
    locked: {
      state: 'LOCKED — 장애물 통과 모드',
      lever: '레버 잠금',
      button: '레버 풀어 해제하기',
      text: '레버를 당기면 캐스터 바퀴 방향이 기계적으로 고정되고, 보조 바퀴가 지지 축 역할을 합니다. ' +
            '바퀴가 옆으로 틀어지지 않아 문턱·틈을 직진 자세 그대로 안전하게 넘어갑니다.'
    }
  };

  var locked = false;

  function renderMech() {
    var copy = locked ? MECH_COPY.locked : MECH_COPY.free;
    mechSvg.classList.toggle('is-locked', locked);
    mechState.classList.toggle('is-locked', locked);
    mechStateText.textContent = copy.state;
    mechLeverLabel.textContent = copy.lever;
    mechBtnLabel.textContent = copy.button;
    mechText.textContent = copy.text;
    mechBtn.setAttribute('aria-pressed', String(locked));
  }

  mechBtn.addEventListener('click', function () {
    locked = !locked;
    renderMech();
  });

  renderMech();

  /* ---------------------------------------------------------
     8. Contact form — Formspree 전송
     --------------------------------------------------------- */
  var form = document.getElementById('contactForm');
  var status = document.getElementById('formStatus');
  var submitBtn = document.getElementById('formSubmit');
  var submitLabel = submitBtn.textContent;
  var EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

  // action에 실제 폼 ID가 들어가기 전까지는 전송을 시도하지 않는다.
  var isConfigured = form.action.indexOf('YOUR_FORM_ID') === -1;

  function setStatus(message, type) {
    status.textContent = message;
    status.className = 'form-status' + (type ? ' is-' + type : '');
  }

  function setBusy(busy) {
    submitBtn.disabled = busy;
    submitBtn.textContent = busy ? '보내는 중…' : submitLabel;
  }

  form.addEventListener('submit', function (e) {
    e.preventDefault();

    var name = form.elements.name;
    var email = form.elements.email;
    var message = form.elements.message;
    var consent = form.elements.consent;

    [name, email, message].forEach(function (f) { f.classList.remove('is-error'); });

    if (!name.value.trim()) {
      name.classList.add('is-error'); name.focus();
      return setStatus('이름 또는 기관명을 입력해 주세요.', 'err');
    }
    if (!EMAIL_RE.test(email.value.trim())) {
      email.classList.add('is-error'); email.focus();
      return setStatus('올바른 이메일 주소를 입력해 주세요.', 'err');
    }
    if (message.value.trim().length < 10) {
      message.classList.add('is-error'); message.focus();
      return setStatus('문의 내용을 10자 이상 입력해 주세요.', 'err');
    }
    if (!consent.checked) {
      consent.focus();
      return setStatus('개인정보 수집·이용에 동의해 주셔야 문의를 보낼 수 있습니다.', 'err');
    }

    if (!isConfigured) {
      // 폼 ID가 없는데 "접수됐다"고 말하면 방문자를 속이는 셈이 된다.
      return setStatus('문의 접수 기능을 준비 중입니다. 잠시 후 다시 시도해 주세요.', 'err');
    }

    setBusy(true);
    setStatus('문의를 보내는 중입니다…', '');

    fetch(form.action, {
      method: 'POST',
      body: new FormData(form),
      headers: { Accept: 'application/json' }
    })
      .then(function (res) {
        if (res.ok) {
          form.reset();
          setStatus('문의가 접수되었습니다. 빠른 시일 내에 회신드리겠습니다.', 'ok');
          return;
        }
        // Formspree는 실패 사유를 errors 배열로 돌려준다.
        return res.json().then(function (data) {
          var reason = data && data.errors && data.errors.length
            ? data.errors.map(function (x) { return x.message; }).join(' ')
            : '';
          setStatus('전송에 실패했습니다. ' + (reason || '잠시 후 다시 시도해 주세요.'), 'err');
        });
      })
      .catch(function () {
        setStatus('네트워크 오류로 전송하지 못했습니다. 연결을 확인한 뒤 다시 시도해 주세요.', 'err');
      })
      .then(function () { setBusy(false); });
  });

  /* ---------------------------------------------------------
     9. Footer year
     --------------------------------------------------------- */
  document.getElementById('year').textContent = new Date().getFullYear();

  // 초기 상태 반영
  onScroll();
})();
