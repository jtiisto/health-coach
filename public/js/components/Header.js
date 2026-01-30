/**
 * Header Component
 */
import { h } from 'preact';
import { useState, useEffect } from 'preact/hooks';
import { effect } from '@preact/signals';
import htm from 'htm';

import { syncStatus, isSyncing, triggerSync } from '../store.js';

const html = htm.bind(h);

export function Header() {
    const [status, setStatus] = useState('gray');
    const [syncing, setSyncing] = useState(false);

    useEffect(() => {
        const dispose = effect(() => {
            setStatus(syncStatus.value);
            setSyncing(isSyncing.value);
        });
        return dispose;
    }, []);

    const handleSyncClick = () => {
        if (!syncing) {
            triggerSync();
        }
    };

    return html`
        <header class="header">
            <h1 class="header-title">Coach</h1>
            <div class="header-actions">
                <div
                    class="sync-indicator ${syncing ? 'syncing' : ''}"
                    onClick=${handleSyncClick}
                    title=${syncing ? 'Syncing...' : 'Click to sync'}
                >
                    <div class="sync-dot ${status}"></div>
                </div>
            </div>
        </header>
    `;
}
