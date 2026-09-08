let questionnaireQuestions = [];
let questionnaireCurrentStep = 0;
let questionnaireAnswers = {};

const questionnaireEls = {
    loading: document.getElementById('loading'),
    header: document.getElementById('header-section'),
    questionView: document.getElementById('question-view'),
    resultsView: document.getElementById('results-view'),
    progressBar: document.getElementById('progress-bar'),
    stepCounter: document.getElementById('step-counter'),
    progressText: document.getElementById('progress-text'),
    title: document.getElementById('question-title'),
    subtitle: document.getElementById('question-subtitle'),
    optionsList: document.getElementById('options-list'),
    btnNext: document.getElementById('btn-next'),
    btnPrev: document.getElementById('btn-prev'),
    careersList: document.getElementById('top-careers-list'),
    reloadButton: document.getElementById('questionnaire-reload'),
    dashboardButton: document.getElementById('questionnaire-go-dashboard'),
};

async function fetchQuestionnaire() {
    try {
        const response = await fetch('/api/v1/questionnaire', {
            credentials: 'include',
        });

        if (response.status === 401 || response.status === 403) {
            window.location.href = '/login';
            return;
        }

        if (!response.ok) {
            throw new Error('Error fetching data');
        }

        const data = await response.json();
        questionnaireQuestions = data.questions;
        initQuestionnaireQuiz();
    } catch (error) {
        alert('Error loading the questionnaire. Make sure you are logged in.');
        console.error(error);
    }
}

async function submitQuestionnaireAnswers() {
    questionnaireEls.questionView.classList.add('hidden');
    questionnaireEls.header.classList.add('hidden');
    questionnaireEls.loading.classList.remove('hidden');
    questionnaireEls.loading.querySelector('p').textContent = 'Calculating your profile...';

    const payload = {
        answers: Object.entries(questionnaireAnswers).map(([questionId, optionId]) => ({
            question_id: questionId,
            option_id: optionId,
        })),
    };

    try {
        const response = await fetch('/api/v1/questionnaire', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            credentials: 'include',
            body: JSON.stringify(payload),
        });

        if (response.status === 401 || response.status === 403) {
            window.location.href = '/login';
            return;
        }

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(`HTTP ${response.status}: ${errorData.detail || 'Unknown error'}`);
        }

        const result = await response.json();
        showQuestionnaireResults(result.top_careers);
    } catch (error) {
        console.error('Error submitting answers:', error);
        alert(`Error submitting answers: ${error.message}`);
        window.location.reload();
    }
}

function initQuestionnaireQuiz() {
    questionnaireEls.loading.classList.add('hidden');
    questionnaireEls.header.classList.remove('hidden');
    questionnaireEls.questionView.classList.remove('hidden');
    renderQuestionnaireStep();
}

function renderQuestionnaireStep() {
    const question = questionnaireQuestions[questionnaireCurrentStep];

    questionnaireEls.title.textContent = question.title;
    questionnaireEls.subtitle.textContent = question.subtitle || '';
    questionnaireEls.stepCounter.textContent = `Question ${questionnaireCurrentStep + 1} of ${questionnaireQuestions.length}`;

    const progress = (questionnaireCurrentStep / questionnaireQuestions.length) * 100;
    questionnaireEls.progressBar.style.width = `${progress}%`;
    questionnaireEls.progressText.textContent = `${Math.round(progress)}%`;

    questionnaireEls.optionsList.innerHTML = '';
    question.options.forEach((option) => {
        const button = document.createElement('div');
        const isSelected = questionnaireAnswers[question.id] === option.id;

        button.className = `option-card p-4 border rounded-xl cursor-pointer transition-all duration-200 flex items-center group ${isSelected ? 'selected border-indigo-600 bg-indigo-50 ring-1 ring-indigo-600' : 'border-gray-200 hover:border-indigo-300'}`;
        button.innerHTML = `
            <div class="w-5 h-5 rounded-full border-2 mr-4 flex items-center justify-center ${isSelected ? 'border-indigo-600 bg-indigo-600' : 'border-gray-300 group-hover:border-indigo-400'}">
                ${isSelected ? '<div class="w-2 h-2 bg-white rounded-full"></div>' : ''}
            </div>
            <span class="font-medium ${isSelected ? 'text-indigo-900' : 'text-gray-700'}">${option.label}</span>
        `;
        button.addEventListener('click', () => selectQuestionnaireOption(question.id, option.id));
        questionnaireEls.optionsList.appendChild(button);
    });

    questionnaireEls.btnPrev.disabled = questionnaireCurrentStep === 0;
    questionnaireEls.btnNext.disabled = !questionnaireAnswers[question.id];
}

function selectQuestionnaireOption(questionId, optionId) {
    questionnaireAnswers[questionId] = optionId;
    renderQuestionnaireStep();
}

function nextQuestionnaireStep() {
    if (questionnaireCurrentStep < questionnaireQuestions.length - 1) {
        questionnaireCurrentStep += 1;
        renderQuestionnaireStep();
        return;
    }

    submitQuestionnaireAnswers();
}

function prevQuestionnaireStep() {
    if (questionnaireCurrentStep > 0) {
        questionnaireCurrentStep -= 1;
        renderQuestionnaireStep();
    }
}

function showQuestionnaireResults(careers) {
    questionnaireEls.loading.classList.add('hidden');
    questionnaireEls.resultsView.classList.remove('hidden');

    const topThree = careers.slice(0, 3);
    questionnaireEls.careersList.innerHTML = topThree.map((career, index) => `
        <div class="bg-white border border-gray-100 p-4 rounded-xl shadow-sm flex items-center">
            <div class="w-10 h-10 rounded-full bg-indigo-100 text-indigo-600 flex items-center justify-center font-bold text-lg mr-4">
                ${index + 1}
            </div>
            <div>
                <h3 class="font-bold text-gray-800">${career.career}</h3>
                <div class="w-full bg-gray-100 h-1.5 rounded-full mt-2 w-32">
                    <div class="bg-indigo-500 h-1.5 rounded-full" style="width: ${Math.min(career.score * 10, 100)}%"></div>
                </div>
            </div>
        </div>
    `).join('');
}

questionnaireEls.btnNext.addEventListener('click', nextQuestionnaireStep);
questionnaireEls.btnPrev.addEventListener('click', prevQuestionnaireStep);
questionnaireEls.reloadButton?.addEventListener('click', () => window.location.reload());
questionnaireEls.dashboardButton?.addEventListener('click', () => {
    window.location.href = '/dashboard';
});

fetchQuestionnaire();
