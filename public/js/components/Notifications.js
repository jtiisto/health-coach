/**
 * Notifications Component - Toast notifications
 */
import { h } from 'preact';
import { useState, useEffect } from 'preact/hooks';
import { effect } from '@preact/signals';
import htm from 'htm';

import { notifications, dismissNotification } from '../store.js';

const html = htm.bind(h);

export function Notifications() {
    const [items, setItems] = useState([]);

    useEffect(() => {
        const dispose = effect(() => {
            setItems([...notifications.value]);
        });
        return dispose;
    }, []);

    if (items.length === 0) {
        return null;
    }

    return html`
        <div class="notifications-container">
            ${items.map(notification => html`
                <div
                    key=${notification.id}
                    class="notification notification-${notification.type}"
                >
                    <div class="notification-content">
                        <div class="notification-title">${notification.title}</div>
                        ${notification.message && html`
                            <div class="notification-message">${notification.message}</div>
                        `}
                    </div>
                    <button
                        class="notification-close"
                        onClick=${() => dismissNotification(notification.id)}
                    >
                        ✕
                    </button>
                </div>
            `)}
        </div>
    `;
}
