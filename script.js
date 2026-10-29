// Trattoria Bella Luna: site interactivity (Hebrew, RTL)

document.addEventListener("DOMContentLoaded", () => {
  const header = document.getElementById("header");
  const navToggle = document.getElementById("navToggle");
  const navMenu = document.getElementById("navMenu");

  // Header background on scroll (FR-1)
  const onScroll = () => header.classList.toggle("scrolled", window.scrollY > 40);
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  // Mobile navigation (FR-2)
  const setNav = (open) => {
    navMenu.classList.toggle("open", open);
    navToggle.setAttribute("aria-expanded", String(open));
  };
  navToggle.addEventListener("click", () => setNav(!navMenu.classList.contains("open")));
  navMenu.querySelectorAll("a").forEach((link) => link.addEventListener("click", () => setNav(false)));
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") setNav(false);
  });

  // Menu category filter (FR-6)
  const tabs = document.querySelectorAll(".tab");
  const dishes = document.querySelectorAll(".dish");
  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      const filter = tab.dataset.filter;
      tabs.forEach((t) => {
        const active = t === tab;
        t.classList.toggle("active", active);
        t.setAttribute("aria-selected", String(active));
      });
      dishes.forEach((dish) => {
        dish.classList.toggle("hidden", filter !== "all" && dish.dataset.category !== filter);
      });
    });
  });

  // Scroll reveal (FR-13)
  const revealEls = document.querySelectorAll(".reveal");
  if ("IntersectionObserver" in window) {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("visible");
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.12 }
    );
    revealEls.forEach((el) => observer.observe(el));
  } else {
    revealEls.forEach((el) => el.classList.add("visible"));
  }

  // Reservation form (FR-8 to FR-10)
  const form = document.getElementById("reserveForm");
  const success = document.getElementById("formSuccess");
  const guests = document.getElementById("guests");
  const dateInput = document.getElementById("date");

  for (let i = 1; i <= 12; i++) {
    const opt = document.createElement("option");
    opt.value = i;
    opt.textContent = i === 1 ? "סועד אחד" : `${i} סועדים`;
    guests.appendChild(opt);
  }

  const todayISO = () => {
    const d = new Date();
    d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
    return d.toISOString().split("T")[0];
  };
  dateInput.min = todayISO();

  const validators = {
    name: (v) => (v.trim().length >= 2 ? "" : "נא להזין שם מלא."),
    email: (v) => (/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v.trim()) ? "" : "נא להזין כתובת אימייל תקינה."),
    phone: (v) => (v.replace(/\D/g, "").length >= 9 ? "" : "נא להזין מספר טלפון תקין."),
    guests: (v) => (v ? "" : "נא לבחור מספר סועדים."),
    date: (v) => {
      if (!v) return "נא לבחור תאריך.";
      if (v < todayISO()) return "לא ניתן לבחור תאריך שעבר.";
      return new Date(`${v}T00:00`).getDay() === 6 ? "מצטערים, אנחנו סגורים בשבת." : "";
    },
    time: (v) => {
      if (!v) return "נא לבחור שעה.";
      return v >= "11:00" && v <= "22:00" ? "" : "ניתן להזמין שולחן בין 11:00 ל־22:00.";
    },
  };

  const validateField = (input) => {
    const check = validators[input.name];
    if (!check) return true;
    const message = check(input.value);
    const field = input.closest(".field");
    field.classList.toggle("invalid", Boolean(message));
    field.querySelector(".error").textContent = message;
    input.setAttribute("aria-invalid", String(Boolean(message)));
    return !message;
  };

  Object.keys(validators).forEach((name) => {
    const input = form.elements[name];
    input.addEventListener("blur", () => validateField(input));
    input.addEventListener("input", () => {
      if (input.closest(".field").classList.contains("invalid")) validateField(input);
    });
  });

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const inputs = Object.keys(validators).map((name) => form.elements[name]);
    const results = inputs.map(validateField);
    if (results.includes(false)) {
      inputs[results.indexOf(false)].focus();
      success.hidden = true;
      return;
    }

    const name = form.elements.name.value.trim().split(" ")[0];
    const date = new Date(`${form.elements.date.value}T00:00`).toLocaleDateString("he-IL", {
      weekday: "long",
      month: "long",
      day: "numeric",
    });
    const guests = Number(form.elements.guests.value);
    const party = guests === 1 ? "לסועד אחד" : `ל־${guests} סועדים`;
    success.textContent = `גראצ׳ה, ${name}! קיבלנו את בקשתך לשולחן ${party} ב${date} בשעה ${form.elements.time.value}. נאשר את ההזמנה באימייל בקרוב.`;
    success.hidden = false;
    form.reset();
  });

  // Footer year (FR-12)
  document.getElementById("year").textContent = new Date().getFullYear();
});
