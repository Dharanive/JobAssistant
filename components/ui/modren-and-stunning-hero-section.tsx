import { useEffect, useRef, useState } from "react";

const PEEPS = [
  "381d6479-f5b5-49ca-82f3-474c87c62996",
  "9df39fca-20db-4273-bf7e-488d04a13321",
  "3c8ee64a-67b3-4a2c-84d5-c665c725e7c5",
  "3ccafa92-f479-4885-a6fb-0af92993b7f6",
  "735686b6-9bd5-4ab1-9fe6-59c50b5e2eb0",
  "3f775475-8920-4f55-b7c1-16bf192a0b1f",
  "b56ceaf5-7fb3-40a2-bb1a-d41c547c71ca",
  "4bd0452d-b321-4488-b57a-0c52dc73ceb1",
  "5d3553c5-a46f-4238-bcb5-02ff60b0f907",
  "6669baf9-e6d8-476b-abd4-e3d52517aee8",
  "2a2fffcb-9e4e-4610-a2ec-c2c334e29001",
  "742a5c0b-c77f-4ab3-96eb-dbca387f5ff8",
  "da0b3073-d6fd-46d2-a1f6-747fbfedf2b1",
  "d9738cd5-9685-47c4-9eab-e004c4d83776",
  "706557e0-8408-4b07-bcab-2968cf4c493e",
].map((id) => `https://floo.design/api/a/${id}.svg`);

const ArrowIcon = () => (
  <svg viewBox="0 0 24 24" className="h-[18px] w-[18px] shrink-0">
    <path
      d="M5 12h14M13 6l6 6-6 6"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

export const Component = () => {
  const crowdRef = useRef<HTMLDivElement | null>(null);
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReducedMotion(media.matches);

    const updateMotion = () => setReducedMotion(media.matches);
    media.addEventListener("change", updateMotion);

    return () => media.removeEventListener("change", updateMotion);
  }, []);

  useEffect(() => {
    const crowd = crowdRef.current;
    if (!crowd) return;

    const things = [
      "profile boost",
      "auto apply",
      "resume skill sync",
      "recruiter visibility",
      "keyword matching",
      "daily applications",
    ];

    const output = document.getElementById("thing");
    let ti = 0;
    let ci = things[0].length;
    let deleting = false;

    if (output) output.textContent = things[0];

    let typingInterval: any;

    if (!reducedMotion) {
      typingInterval = setInterval(() => {
        const word = things[ti];

        if (!deleting) {
          ci++;
          if (ci > word.length) {
            deleting = true;
            ci = word.length + 8;
          }
        } else {
          ci--;
          if (ci < 0) {
            deleting = false;
            ti = (ti + 1) % things.length;
            ci = 0;
          }
        }

        if (output) {
          output.textContent = word.slice(
            0,
            Math.max(0, Math.min(ci, word.length))
          );
        }
      }, 70);
    }

    const people: Array<{ wrapper: HTMLDivElement; element: HTMLDivElement; image: HTMLImageElement; t?: number; dir?: number; speed?: number; x?: number; depth?: number }> = [];
    let mx = 0;
    let tx = 0;
    let last = performance.now();
    let frame: number;

    const place = (person: any, anywhere = false) => {
      person.t = 31 + Math.random() * 54;

      const width = 146 + (person.t - 31.8) * 2.62;

      person.dir = Math.random() < 0.5 ? 1 : -1;
      person.speed = 108 / (9 + Math.random() * 27);
      person.x = anywhere
        ? -5 + Math.random() * 110
        : person.dir > 0
          ? -5
          : 104;

      person.depth = (person.t - 31) / 54;

      person.wrapper.style.cssText = `
        top:${person.t.toFixed(2)}%;
        width:${width.toFixed(1)}px;
        height:${(width * 1.35).toFixed(1)}px;
        z-index:${Math.floor(person.t)};
      `;

      person.image.src =
        PEEPS[Math.floor(Math.random() * PEEPS.length)];

      person.image.style.filter = `blur(${Math.max(
        0.04,
        (78 - person.t) * 0.05
      ).toFixed(2)}px)`;

      person.image.style.transform = `scaleX(${person.dir})`;
    };

    for (let i = 0; i < 64; i++) {
      const wrapper = document.createElement("div");
      wrapper.className = "absolute left-0 will-change-transform";

      const element = document.createElement("div");
      element.className =
        "h-full w-full will-change-transform [backface-visibility:hidden]";

      const img = document.createElement("img");
      img.alt = "";
      img.draggable = false;
      img.decoding = "async";
      img.className = "block h-full w-full";

      element.appendChild(img);
      wrapper.appendChild(element);
      crowd.appendChild(wrapper);

      const person = { wrapper, element, image: img };
      place(person, true);
      people.push(person);
    }

    const handlePointerMove = (event: PointerEvent) => {
      tx = event.clientX / window.innerWidth - 0.5;
    };

    window.addEventListener("pointermove", handlePointerMove);

    const animate = (now: number) => {
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      mx += (tx - mx) * 0.06;

      people.forEach((person: any) => {
        if (!reducedMotion) {
          person.x += person.dir * person.speed * dt;

          if (person.x > 104 || person.x < -6) {
            place(person);
          }
        }

        person.element.style.transform =
          `translate3d(calc(-50% + ${person.x.toFixed(2)}vw), -50%, 0)`;

        person.wrapper.style.transform =
          `translate3d(${(-mx * person.depth * 3).toFixed(2)}vw, 0, 0)`;
      });

      if (!reducedMotion) {
        frame = requestAnimationFrame(animate);
      }
    };

    if (!reducedMotion) {
      frame = requestAnimationFrame(animate);
    }

    return () => {
      if (typingInterval) clearInterval(typingInterval);
      cancelAnimationFrame(frame);
      window.removeEventListener("pointermove", handlePointerMove);
      crowd.innerHTML = "";
    };
  }, [reducedMotion]);

  return (
    <div className="relative isolate min-h-screen w-full overflow-hidden bg-[#000] font-sans text-[#ededef] antialiased">

      {/* Background glow - Orange / Amber */}
      <div className="pointer-events-none absolute left-1/2 top-[-260px] -ml-[450px] h-[760px] w-[900px] animate-orb-spin rounded-full bg-[conic-gradient(from_0deg,#ff9900,#f97316,#ea580c,#facc15,#ff9900)] opacity-[0.25] blur-[150px]" />

      {/* Navigation */}
      <header className="absolute left-0 right-0 top-0 z-20 h-20">
        <div className="mx-auto flex h-full max-w-[1220px] items-center justify-between px-6">

          <a href="#" className="shrink-0 flex items-center gap-2">
            <span className="text-2xl font-black tracking-tight text-white">
              k<span className="text-orange-500">l</span>yck
            </span>
          </a>

          <nav className="hidden items-center gap-8 text-base text-gray-400 md:flex">
            <a href="#" className="transition-colors hover:text-white">Profile Boost</a>
            <a href="#" className="transition-colors hover:text-white">Auto Apply</a>
            <a href="#" className="transition-colors hover:text-white">Skill Sync</a>
            <a href="#" className="transition-colors hover:text-white">Live Logs</a>
          </nav>

          <div className="flex items-center gap-3.5">
            <a
              href="#"
              className="inline-flex h-[38px] items-center rounded-lg bg-gradient-to-r from-orange-500 to-amber-500 px-4 text-sm font-semibold text-white shadow-md transition hover:brightness-110"
            >
              Connect Naukri
            </a>
          </div>
        </div>
      </header>

      {/* Hero */}
      <main className="relative z-[5] px-5 pb-24 pt-[112px] text-center">

        <h1 className="animate-rise text-[clamp(48px,6.4vw,82px)] font-bold leading-[0.98] tracking-[-3.6px] text-white">
          Supercharge your job hunt
          <br />

          <span className="relative inline-block text-white">
            on autopilot.

            <svg
              viewBox="0 0 520 22"
              preserveAspectRatio="none"
              className="absolute -bottom-[14px] left-[-1%] h-[22px] w-[102%] overflow-visible"
            >
              <defs>
                <linearGradient id="underline-gradient" x1="0" x2="1">
                  <stop stopColor="#fb923c" />
                  <stop offset=".5" stopColor="#f97316" />
                  <stop offset="1" stopColor="#ea580c" />
                </linearGradient>
              </defs>
              <path
                pathLength="1"
                d="M6 14C120 4 300 3 514 12"
                className="animate-underline-draw fill-none stroke-[5] [stroke:url(#underline-gradient)] [stroke-linecap:round] [stroke-dasharray:1] [stroke-dashoffset:1]"
              />
            </svg>
          </span>
        </h1>

        <p className="mx-auto mt-[30px] max-w-[720px] animate-rise text-[19px] leading-[1.55] text-gray-300">
          Boost your Naukri recruiter search ranking daily, auto-apply to targeted roles with smart keyword filtering, sync resume skills, and stream real-time browser execution.
        </p>

        {/* CTA buttons */}
        <div className="mt-[30px] flex animate-rise flex-col justify-center gap-3 sm:flex-row sm:gap-5">

          <a
            href="#"
            className="group relative inline-flex h-14 items-center justify-center gap-2.5 overflow-hidden rounded-xl bg-gradient-to-b from-[#f97316] to-[#ea580c] px-[34px] text-[17px] font-bold text-white shadow-[inset_0_1px_0_rgba(255,255,255,.35),0_0_0_1px_rgba(249,115,22,.6),0_16px_40px_-12px_rgba(249,115,22,.75)] transition hover:brightness-110"
          >
            <span className="absolute inset-y-0 -left-[60%] w-[40%] skew-x-[-20deg] animate-button-sweep bg-gradient-to-r from-transparent via-white/50 to-transparent" />
            <span className="relative">Start Automating</span>
            <span className="relative transition-transform group-hover:translate-x-[3px]">
              <ArrowIcon />
            </span>
          </a>

          <a
            href="#live-console-sec"
            className="inline-flex h-14 items-center justify-center gap-2.5 rounded-xl border border-white/[0.14] bg-white/[0.04] px-[30px] text-[17px] font-bold text-white transition hover:bg-white/[0.08]"
          >
            <svg viewBox="0 0 24 24" className="h-[18px] w-[18px]">
              <path fill="#f97316" d="M7 4.5v15l13-7.5z" />
            </svg>
            Watch Live Stream
          </a>
        </div>

        {/* Composer */}
        <div className="relative mx-auto mt-[34px] w-full max-w-[640px] animate-rise">
          <div className="absolute -inset-x-[140px] -inset-y-[30px] -z-10 bg-[radial-gradient(closest-side,rgba(0,0,0,.85),transparent)]" />

          <h2 className="font-['Caveat',cursive] text-[34px] font-bold leading-tight text-white">
            Connect your account. Let KLyck work.
          </h2>

          <p className="mb-4 mt-2 text-[15px] text-gray-400">
            Select platform first and enter credentials to unlock automated profile boosting & 1-click applies.
          </p>

          <div className="relative rounded-2xl bg-[#121215] p-3 pl-[18px] text-left shadow-[0_30px_60px_-20px_rgba(0,0,0,.95)] border border-orange-500/30">
            <div className="flex items-center gap-2.5">
              <div className="min-w-0 flex-1 text-[17px] text-[#a1a1aa]">
                Let’s automate{" "}
                <b id="thing" className="font-semibold text-orange-400">
                  profile boost
                </b>
                <i className="ml-0.5 inline-block h-[19px] w-0.5 animate-caret-blink bg-orange-500 align-[-3px]" />
              </div>

              <button
                type="button"
                className="inline-flex h-[42px] shrink-0 items-center gap-2 rounded-[10px] bg-gradient-to-r from-orange-500 to-amber-500 px-[18px] text-[15px] font-semibold text-white shadow-md transition hover:brightness-110"
              >
                Connect <ArrowIcon />
              </button>
            </div>
          </div>
        </div>
      </main>

      {/* Animated walking characters */}
      <div
        ref={crowdRef}
        className="pointer-events-none absolute bottom-0 left-0 right-0 z-[3] h-[40vh] overflow-hidden"
        aria-hidden="true"
      />
    </div>
  );
};

export default Component;
