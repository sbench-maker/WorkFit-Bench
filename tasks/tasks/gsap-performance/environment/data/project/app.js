export function mountIncidentWall({ root = document, win = window, gsap, ScrollTrigger }) {
  const board = root.querySelector(".incident-board");
  const halo = root.querySelector(".cursor-halo");
  const drawer = root.querySelector(".detail-drawer");
  const openButton = root.querySelector('[data-action="open-drawer"]');
  const closeButton = root.querySelector('[data-action="close-drawer"]');
  const cards = Array.from(root.querySelectorAll(".incident-card"));
  const reduced = win.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function revealVisibleCards() {
    cards.forEach((card, index) => {
      const rect = card.getBoundingClientRect();
      if (rect.bottom >= 0 && rect.top <= win.innerHeight && card.dataset.revealed !== "true") {
        card.dataset.revealed = "true";
        gsap.fromTo(
          card,
          { top: 24, opacity: 0 },
          {
            top: 0,
            opacity: 1,
            duration: reduced ? 0 : 0.42,
            ease: "power2.out",
            delay: index * 0.018
          }
        );
      }
    });
  }

  function moveHalo(event) {
    const boardRect = board.getBoundingClientRect();
    gsap.to(halo, {
      left: event.clientX - boardRect.left,
      top: event.clientY - boardRect.top,
      duration: reduced ? 0 : 0.18,
      ease: "power3.out",
      overwrite: true
    });
  }

  function openDrawer() {
    drawer.dataset.state = "open";
    drawer.setAttribute("aria-hidden", "false");
    gsap.to(drawer, {
      right: 0,
      width: 360,
      duration: reduced ? 0 : 0.32,
      ease: "power2.out"
    });
  }

  function closeDrawer() {
    drawer.dataset.state = "closed";
    drawer.setAttribute("aria-hidden", "true");
    gsap.to(drawer, {
      right: -360,
      width: 360,
      duration: reduced ? 0 : 0.32,
      ease: "power2.in"
    });
  }

  function refreshOnResize() {
    ScrollTrigger.refresh();
  }

  gsap.set(drawer, { right: -360, width: 360 });
  revealVisibleCards();
  board.addEventListener("pointermove", moveHalo);
  win.addEventListener("scroll", revealVisibleCards);
  win.addEventListener("resize", refreshOnResize);
  openButton.addEventListener("click", openDrawer);
  closeButton.addEventListener("click", closeDrawer);

  return function cleanup() {
    // TODO: production controller must release event handlers and active work.
  };
}
