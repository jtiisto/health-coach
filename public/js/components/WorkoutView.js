/**
 * Workout View Component - Main exercise list
 */
import { h } from 'preact';
import htm from 'htm';

import { ExerciseItem } from './ExerciseItem.js';
import { SessionFeedback } from './SessionFeedback.js';

const html = htm.bind(h);

export function WorkoutView({ date, plan, log }) {
    if (!plan) {
        return html`
            <div class="empty-state">
                <div class="empty-state-icon">📋</div>
                <p class="empty-state-text">No workout scheduled for this day</p>
            </div>
        `;
    }

    const exercises = plan.exercises || [];

    return html`
        <div class="workout-view">
            <div class="workout-header">
                <h2 class="workout-day-name">${plan.day_name || 'Workout'}</h2>
                <div class="workout-meta">
                    ${plan.location && html`
                        <span class="workout-meta-item">
                            <span class="icon">📍</span>
                            ${plan.location}
                        </span>
                    `}
                    ${plan.phase && html`
                        <span class="workout-meta-item">
                            <span class="icon">📊</span>
                            ${plan.phase}
                        </span>
                    `}
                </div>
            </div>

            <div class="exercises-list">
                ${exercises.map(exercise => html`
                    <${ExerciseItem}
                        key=${exercise.id}
                        date=${date}
                        exercise=${exercise}
                        logData=${log?.[exercise.id]}
                    />
                `)}
            </div>

            <${SessionFeedback}
                date=${date}
                feedback=${log?.session_feedback || {}}
            />
        </div>
    `;
}
