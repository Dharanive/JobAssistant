import React, { useImperativeHandle, forwardRef, useRef, useEffect } from 'react';

export type NotificationType = 'help' | 'success' | 'warning' | 'error';

export interface SplashedPushNotificationsHandle {
  createNotification: (type: NotificationType, title: string, content: string) => void;
  createRtlNotification: (type: NotificationType, title: string, content: string) => void;
}

export interface SplashedPushNotificationsProps {
  timerColor?: string;    // Color of the running timer (the progress bar)
  timerBgColor?: string;  // Background color of the timer bar
}

// SVGs as strings (updated per your request)
const ICON_SVGS: Record<NotificationType, string> = {
  success: `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-check-check-icon lucide-check-check"><path d="M18 6 7 17l-5-5"/><path d="m22 10-7.5 7.5L13 16"/></svg>`,
  help: `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-message-circle-question-icon lucide-message-circle-question"><path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><path d="M12 17h.01"/></svg>`,
  warning: `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-zap-icon lucide-zap"><path d="M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z"/></svg>`,
  error: `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-shield-x-icon lucide-shield-x"><path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m14.5 9.5-5 5"/><path d="m9.5 9.5 5 5"/></svg>`,
};

const CLOSE_SVG = `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-x-icon lucide-x"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>`;

export const SplashedPushNotifications = forwardRef<SplashedPushNotificationsHandle, SplashedPushNotificationsProps>(
  ({ timerColor, timerBgColor }, ref) => {
    const notificationContainerRef = useRef<HTMLDivElement | null>(null);
    const rtlNotificationContainerRef = useRef<HTMLDivElement | null>(null);

    useEffect(() => {
      if (document.getElementById('splashed-toast-css')) return;
      const style = document.createElement('style');
      style.id = 'splashed-toast-css';
      style.innerHTML = `
        .wrapper { margin: 0; padding: 0; width: 100vw; height: 100vh; overflow: hidden; display: flex; align-items: center; justify-content: center; flex-direction: column; }
        .buttonContainer { display: flex; }
        .buttonContainer button { background-color: #fff; font-weight: bold; color: #1d2232; cursor: pointer; font-family: inherit; padding: 1rem; border-radius: 5px; border: 3px solid #fff; margin:14px; }
        .buttonContainer button:hover { transform: scale(1.05); border: 3px solid #007fff; }
        .notificationContainer { display: flex; flex-direction: column; align-items: flex-end; position: fixed; bottom: 10px; right: 10px; max-width: 355px; z-index: 999999; }
        .rtlNotifications{ left: 10px; right: auto; transform: scale(-1, 1); }
        .toast { color: #f5f5f5; padding: 1.5rem 2rem; border-radius: 4px; background-color: #1d2232; transition: transform 0.8s ease; animation: appear 0.5s ease forwards; display: flex; align-items: center; justify-content: space-between; overflow: hidden; position: relative; margin-bottom: 10px; }
        .rtlNotifications .toast { transform: scale(-1, 1); }
        .toastContent { width: 100%; display: flex; align-items: center; }
        .toastTitle { font-weight: bold; margin-bottom: 0.2rem; }
        .toastText { font-size: 0.9rem; }
        .timer { position: absolute; bottom: 0; left: 0; height: 5px; width: 100%; animation: timer 4s linear forwards; }
        @keyframes timer { 0% { width: 100%; } 100% { width: 0%; } }
        .bounceEffect { animation: bounce 1.5s ease-in-out infinite; }
        @keyframes appear { 0% { transform: translateY(200px); opacity: 0; } 100% { transform: translateY(0px); opacity: 1; } }
        @keyframes bounce { 0%, 20%, 50%, 80%, 100% { transform: translateY(0); } 40% { transform: translateY(-5px); } 60% { transform: translateY(-3px); } }
        .closeBtn { margin-left: 1.5rem; cursor: pointer; }
        .success { background-color: #00ca72; }
        .warning { background-color: #ff9900; }
        .error { background-color: #ff4743; }
        .help { background-color: #007fff; }
      `;
      document.head.appendChild(style);
    }, []);

    const removeNotification = (toast: HTMLElement) => {
      toast.style.animation = 'appear 0.5s ease reverse forwards';
      setTimeout(() => {
        toast.remove();
      }, 500);
    };

    const createNotification = (type: NotificationType, title: string, content: string) => {
      const icon = ICON_SVGS[type];
      const toast = document.createElement('div');
      toast.classList.add('toast', type);

      const resolvedTimerColor = timerColor || (type === 'warning' ? '#c24914' : '#fff');
      const resolvedTimerBgColor = timerBgColor || (type === 'warning' ? '#fc8621' : '#0000003a');

      toast.innerHTML = `
        <div class="toastContent">
          <div class="bounceEffect">${icon}</div>
          <div style="margin-left: 1.5rem;">
            <div class="toastTitle">${title}</div>
            <div class="toastText">${content}</div>
          </div>
        </div>
        <div class="closeBtn">${CLOSE_SVG}</div>
        <div class="timer" style="background-color: ${resolvedTimerColor};">
          <div style="background-color: ${resolvedTimerBgColor}; width: 100%; height: 100%;"></div>
        </div>
      `;

      const closeBtn = toast.querySelector('.closeBtn');
      closeBtn?.addEventListener('click', () => removeNotification(toast));

      notificationContainerRef.current?.appendChild(toast);

      setTimeout(() => {
        removeNotification(toast);
      }, 4000);
    };

    const createRtlNotification = (type: NotificationType, title: string, content: string) => {
      const icon = ICON_SVGS[type];
      const toast = document.createElement('div');
      toast.classList.add('toast', type);

      const resolvedTimerColor = timerColor || (type === 'warning' ? '#c24914' : '#fff');
      const resolvedTimerBgColor = timerBgColor || (type === 'warning' ? '#fc8621' : '#0000003a');

      toast.innerHTML = `
        <div class="toastContent">
          <div class="bounceEffect">${icon}</div>
          <div style="margin-left: 1.5rem;">
            <div class="toastTitle">${title}</div>
            <div class="toastText">${content}</div>
          </div>
        </div>
        <div class="closeBtn">${CLOSE_SVG}</div>
        <div class="timer" style="background-color: ${resolvedTimerColor};">
          <div style="background-color: ${resolvedTimerBgColor}; width: 100%; height: 100%;"></div>
        </div>
      `;

      const closeBtn = toast.querySelector('.closeBtn');
      closeBtn?.addEventListener('click', () => removeNotification(toast));

      rtlNotificationContainerRef.current?.appendChild(toast);

      setTimeout(() => {
        removeNotification(toast);
      }, 4000);
    };

    useImperativeHandle(ref, () => ({
      createNotification,
      createRtlNotification,
    }));

    return (
      <>
        <div ref={notificationContainerRef} className="notificationContainer" />
        <div ref={rtlNotificationContainerRef} className="notificationContainer rtlNotifications" />
      </>
    );
  }
);

SplashedPushNotifications.displayName = 'SplashedPushNotifications';

export default SplashedPushNotifications;
