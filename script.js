const FALLBACK_BACKEND_URL = "https://ia-previsao-ritmo-backend.onrender.com";

const dateFormatter = new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
});

const numberFormatter = new Intl.NumberFormat("pt-BR", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
});

const compactFormatter = new Intl.NumberFormat("pt-BR", {
    notation: "compact",
    maximumFractionDigits: 1,
});

const refs = {};
const state = {
    apiBaseUrl: "",
    health: null,
    prediction: null,
};


document.addEventListener("DOMContentLoaded", async () => {
    cacheRefs();
    state.apiBaseUrl = resolveBackendUrl();
    bindEvents();
    await bootstrapDashboard();
});


function cacheRefs() {
    refs.form = document.getElementById("predictionForm");
    refs.predictionDateInput = document.getElementById("predictionDate");
    refs.fetchDataButton = document.getElementById("fetchDataButton");
    refs.loadingSection = document.getElementById("loading");
    refs.predictionResultsSection = document.getElementById("predictionResults");
    refs.errorDisplaySection = document.getElementById("errorDisplay");
    refs.errorMessage = document.getElementById("errorMessage");
    refs.errorDetails = document.getElementById("errorDetails");

    refs.systemStatusLabel = document.getElementById("systemStatusLabel");
    refs.forecastWindowLabel = document.getElementById("forecastWindowLabel");
    refs.lastUpdatedLabel = document.getElementById("lastUpdatedLabel");
    refs.controlHelperText = document.getElementById("controlHelperText");

    refs.historicalWindowValue = document.getElementById("historicalWindowValue");
    refs.recordsValue = document.getElementById("recordsValue");
    refs.driversValue = document.getElementById("driversValue");
    refs.eventTypesValue = document.getElementById("eventTypesValue");

    refs.forecastTotalValue = document.getElementById("forecastTotalValue");
    refs.forecastDateValue = document.getElementById("forecastDateValue");
    refs.riskLevelValue = document.getElementById("riskLevelValue");
    refs.riskVariationValue = document.getElementById("riskVariationValue");
    refs.historicalAverageValue = document.getElementById("historicalAverageValue");
    refs.historicalPeakValue = document.getElementById("historicalPeakValue");
    refs.priorityTargetValue = document.getElementById("priorityTargetValue");
    refs.prioritySupportValue = document.getElementById("prioritySupportValue");

    refs.executiveTitle = document.getElementById("executiveTitle");
    refs.executiveSummary = document.getElementById("executiveSummary");
    refs.riskPill = document.getElementById("riskPill");
    refs.trendWindowLabel = document.getElementById("trendWindowLabel");
    refs.trendBars = document.getElementById("trendBars");
    refs.insightsList = document.getElementById("insightsList");
    refs.podiumGrid = document.getElementById("podiumGrid");
    refs.topDriversList = document.getElementById("topDriversList");
    refs.localitiesList = document.getElementById("localitiesList");
    refs.eventTypesBars = document.getElementById("eventTypesBars");
    refs.eventBreakdownGrid = document.getElementById("eventBreakdownGrid");
}


function bindEvents() {
    refs.form.addEventListener("submit", async (event) => {
        event.preventDefault();
        await loadPrediction();
    });
}


async function bootstrapDashboard() {
    setSystemStatus("Conectando ao backend preditivo");
    setLoading(true);
    clearError();

    try {
        await loadHealth();
    } catch (error) {
        refs.predictionDateInput.value =
            refs.predictionDateInput.value || formatInputDate(addDays(new Date(), 1));
        setSystemStatus("Healthcheck indisponivel, tentando consulta direta");
    }

    await loadPrediction();
}


function resolveBackendUrl() {
    const queryApi = new URLSearchParams(window.location.search).get("api");
    if (queryApi) {
        return queryApi.replace(/\/$/, "");
    }

    if (window.location.protocol === "file:") {
        return FALLBACK_BACKEND_URL;
    }

    if (["localhost", "127.0.0.1"].includes(window.location.hostname)) {
        return "http://127.0.0.1:5000";
    }

    return FALLBACK_BACKEND_URL;
}


async function loadHealth() {
    const response = await fetch(`${state.apiBaseUrl}/health`);
    if (!response.ok) {
        throw new Error("Nao foi possivel consultar a saude do backend.");
    }

    state.health = await response.json();
    const health = state.health;

    setSystemStatus(
        health.model_ready
            ? "Motor preditivo pronto para consulta"
            : "Backend conectado, mas o modelo ainda nao esta pronto"
    );

    if (!refs.predictionDateInput.value && health.suggested_prediction_date) {
        refs.predictionDateInput.value = health.suggested_prediction_date;
    } else if (!refs.predictionDateInput.value) {
        refs.predictionDateInput.value = formatInputDate(addDays(new Date(), 1));
    }

    if (health.suggested_prediction_date && health.forecast_days) {
        const forecastStart = parseIsoDate(health.suggested_prediction_date);
        const forecastEnd = addDays(forecastStart, health.forecast_days - 1);
        refs.forecastWindowLabel.textContent =
            `${formatDate(health.suggested_prediction_date)} ate ${formatDate(formatInputDate(forecastEnd))}`;
    }

    if (health.historical_window?.start && health.historical_window?.end) {
        refs.historicalWindowValue.textContent =
            `${formatDate(health.historical_window.start)} ate ${formatDate(health.historical_window.end)}`;
    }

    refs.recordsValue.textContent = formatCompact(health.records_loaded);
    refs.controlHelperText.textContent = health.suggested_prediction_date
        ? "A data inicial foi posicionada automaticamente na primeira janela de previsao disponivel."
        : "Selecione uma data dentro da janela prevista pelo modelo.";
}


async function loadPrediction() {
    const selectedDate = refs.predictionDateInput.value;
    if (!selectedDate) {
        handleError({
            message: "Selecione uma data para atualizar o painel.",
            details: "A previsao depende de uma data no formato YYYY-MM-DD.",
        });
        return;
    }

    setLoading(true);
    clearError();

    try {
        const response = await fetch(`${state.apiBaseUrl}/predict?date=${selectedDate}`);
        const payload = await response.json();

        if (!response.ok) {
            throw {
                status: response.status,
                payload,
            };
        }

        state.prediction = payload;
        renderDashboard(payload);
        refs.predictionResultsSection.classList.remove("hidden");
        setSystemStatus("Painel sincronizado com a ultima previsao");
    } catch (error) {
        handleError(error);
    } finally {
        setLoading(false);
    }
}


function renderDashboard(payload) {
    renderContext(payload);
    renderMetrics(payload);
    renderExecutivePanel(payload);
    renderInsights(payload.insights_prioritarios || []);
    renderPodium(payload.top_10_motoristas_geral || []);
    renderRankedStack(
        refs.topDriversList,
        payload.top_10_motoristas_geral || [],
        {
            labelKey: "Motorista",
            subtitle: (item) =>
                `${formatPercent(item.ParticipacaoPercentual)} do historico | ${formatDecimal(item.EventosEsperados)} eventos esperados`,
        }
    );
    renderRankedStack(
        refs.localitiesList,
        payload.top_3_localidades || [],
        {
            labelKey: "Localidade",
            subtitle: (item) =>
                `${formatPercent(item.ParticipacaoPercentual)} de concentracao | ${formatDecimal(item.EventosEsperados)} eventos esperados`,
        }
    );
    renderEventTypes(payload.top_tipos_evento || []);
    renderEventBreakdown(payload.probabilidade_eventos_especificos || {});
}


function renderContext(payload) {
    const context = payload.dataset_contexto || {};

    refs.forecastWindowLabel.textContent =
        `${formatDate(payload.forecast_period_start)} ate ${formatDate(payload.forecast_period_end)}`;
    refs.lastUpdatedLabel.textContent = context.ultima_atualizacao_arquivo || "Nao informado";
    refs.historicalWindowValue.textContent =
        context.janela_historica_inicio && context.janela_historica_fim
            ? `${formatDate(context.janela_historica_inicio)} ate ${formatDate(context.janela_historica_fim)}`
            : "-";
    refs.recordsValue.textContent = formatCompact(context.total_registros);
    refs.driversValue.textContent = formatCompact(context.motoristas_monitorados);
    refs.eventTypesValue.textContent = formatCompact(context.tipos_evento_monitorados);
    refs.controlHelperText.textContent =
        `Janela prevista: ${formatDate(payload.forecast_period_start)} ate ${formatDate(payload.forecast_period_end)}.`;
}


function renderMetrics(payload) {
    const summary = payload.resumo_executivo || {};
    const priorityPieces = [
        summary.localidade_critica,
        summary.tipo_evento_lider,
    ].filter(Boolean);

    refs.forecastTotalValue.textContent = formatDecimal(payload.previsao_total_yhat1);
    refs.forecastDateValue.textContent = `Cenario de ${formatDate(payload.data_previsao)}`;
    refs.riskLevelValue.textContent = formatRisk(summary.nivel_risco);
    refs.riskVariationValue.textContent = summary.variacao_media_percentual === null
        ? "Sem comparativo"
        : `${formatSignedPercent(summary.variacao_media_percentual)} vs media diaria`;
    refs.historicalAverageValue.textContent = formatDecimal(summary.media_diaria_historica);
    refs.historicalPeakValue.textContent = summary.pico_diario_historico === null
        ? "Pico historico indisponivel"
        : `Pico historico: ${formatDecimal(summary.pico_diario_historico)} eventos/dia`;
    refs.priorityTargetValue.textContent = summary.motorista_prioritario || "Sem motorista critico";
    refs.prioritySupportValue.textContent = priorityPieces.length
        ? priorityPieces.join(" | ")
        : "Aguardando identificacao de hotspot";
}


function renderExecutivePanel(payload) {
    const summary = payload.resumo_executivo || {};
    const insights = payload.insights_prioritarios || [];
    const recentSeries = payload.serie_historica_recente || [];

    refs.executiveTitle.textContent = `Cenario para ${formatDate(payload.data_previsao)}`;
    refs.executiveSummary.textContent =
        insights[0] ||
        `A previsao aponta ${formatDecimal(payload.previsao_total_yhat1)} eventos para a data selecionada.`;

    refs.riskPill.textContent = formatRisk(summary.nivel_risco);
    refs.riskPill.dataset.risk = summary.nivel_risco || "";

    if (recentSeries.length > 0) {
        refs.trendWindowLabel.textContent =
            `${formatDate(recentSeries[0].data)} ate ${formatDate(recentSeries[recentSeries.length - 1].data)}`;
    } else {
        refs.trendWindowLabel.textContent = "Sem serie recente";
    }

    renderTrendBars(recentSeries);
}


function renderInsights(insights) {
    refs.insightsList.innerHTML = "";

    if (!insights.length) {
        refs.insightsList.appendChild(createEmptyListItem("Nenhum insight prioritario foi retornado."));
        return;
    }

    insights.forEach((insight) => {
        const item = document.createElement("li");
        item.textContent = insight;
        refs.insightsList.appendChild(item);
    });
}


function renderTrendBars(series) {
    refs.trendBars.innerHTML = "";

    if (!series.length) {
        refs.trendBars.appendChild(createEmptyCard("Sem historico recente para montar a tendencia."));
        return;
    }

    const maxValue = Math.max(...series.map((item) => Number(item.total) || 0), 1);

    series.forEach((item) => {
        const wrapper = document.createElement("article");
        wrapper.className = "trend-bar";

        const value = document.createElement("span");
        value.className = "trend-bar-value";
        value.textContent = formatDecimal(item.total);

        const fill = document.createElement("div");
        fill.className = "trend-bar-fill";
        fill.style.height = `${Math.max((Number(item.total) / maxValue) * 100, 10)}%`;

        const label = document.createElement("span");
        label.className = "trend-bar-label";
        label.textContent = shortDateLabel(item.data);

        wrapper.append(value, fill, label);
        refs.trendBars.appendChild(wrapper);
    });
}


function renderPodium(drivers) {
    refs.podiumGrid.innerHTML = "";
    const podiumDrivers = drivers.slice(0, 3);

    if (!podiumDrivers.length) {
        refs.podiumGrid.appendChild(createEmptyCard("Nenhum motorista disponivel para o podio."));
        return;
    }

    podiumDrivers.forEach((driver, index) => {
        const card = document.createElement("article");
        card.className = "podium-card";

        const rank = document.createElement("span");
        rank.className = "podium-rank";
        rank.textContent = `#${index + 1}`;

        const name = document.createElement("strong");
        name.className = "podium-name";
        name.textContent = driver.Motorista;

        const value = document.createElement("span");
        value.className = "podium-value";
        value.textContent = formatPercent(driver.ParticipacaoPercentual);

        const support = document.createElement("span");
        support.className = "podium-support";
        support.textContent =
            `${formatDecimal(driver.EventosEsperados)} eventos esperados | ${formatCompact(driver.VolumeHistorico)} registros historicos`;

        card.append(rank, name, value, support);
        refs.podiumGrid.appendChild(card);
    });
}


function renderRankedStack(container, items, options) {
    container.innerHTML = "";

    if (!items.length) {
        container.appendChild(createEmptyCard("Nao ha dados suficientes para exibir esta lista."));
        return;
    }

    const maxPercent = Math.max(
        ...items.map((item) => Number(item.ParticipacaoPercentual || item.Probabilidade || 0)),
        1
    );

    items.forEach((item, index) => {
        const card = document.createElement("article");
        card.className = "stack-item";

        const header = document.createElement("div");
        header.className = "stack-item-header";

        const title = document.createElement("strong");
        title.className = "stack-item-title";
        title.textContent = `${index + 1}. ${item[options.labelKey]}`;

        const score = document.createElement("span");
        score.className = "stack-item-subtitle";
        score.textContent = formatPercent(item.ParticipacaoPercentual || item.Probabilidade);

        header.append(title, score);

        const subtitle = document.createElement("p");
        subtitle.className = "stack-item-subtitle";
        subtitle.textContent = options.subtitle(item);

        const progress = document.createElement("div");
        progress.className = "inline-progress";

        const progressFill = document.createElement("span");
        progressFill.style.width =
            `${Math.max(((item.ParticipacaoPercentual || item.Probabilidade || 0) / maxPercent) * 100, 8)}%`;
        progress.appendChild(progressFill);

        const footer = document.createElement("div");
        footer.className = "stack-item-footer";
        footer.textContent = `${formatCompact(item.VolumeHistorico)} ocorrencias historicas consideradas`;

        card.append(header, subtitle, progress, footer);
        container.appendChild(card);
    });
}


function renderEventTypes(eventTypes) {
    refs.eventTypesBars.innerHTML = "";

    if (!eventTypes.length) {
        refs.eventTypesBars.appendChild(createEmptyCard("Nenhum tipo de evento foi retornado."));
        return;
    }

    const maxPercent = Math.max(
        ...eventTypes.map((item) => Number(item.ParticipacaoPercentual || 0)),
        1
    );

    eventTypes.forEach((eventType) => {
        const wrapper = document.createElement("article");
        wrapper.className = "bar-item";

        const header = document.createElement("div");
        header.className = "bar-item-header";

        const label = document.createElement("strong");
        label.className = "bar-item-label";
        label.textContent = eventType.TipoEvento;

        const score = document.createElement("span");
        score.className = "stack-item-subtitle";
        score.textContent = formatPercent(eventType.ParticipacaoPercentual);

        header.append(label, score);

        const track = document.createElement("div");
        track.className = "bar-track";

        const fill = document.createElement("span");
        fill.style.width = `${Math.max((eventType.ParticipacaoPercentual / maxPercent) * 100, 10)}%`;
        track.appendChild(fill);

        const meta = document.createElement("p");
        meta.className = "bar-item-meta";
        meta.textContent =
            `${formatDecimal(eventType.EventosEsperados)} eventos esperados | ${formatCompact(eventType.VolumeHistorico)} registros historicos`;

        wrapper.append(header, track, meta);
        refs.eventTypesBars.appendChild(wrapper);
    });
}


function renderEventBreakdown(eventGroups) {
    refs.eventBreakdownGrid.innerHTML = "";
    const entries = Object.entries(eventGroups);

    if (!entries.length) {
        refs.eventBreakdownGrid.appendChild(
            createEmptyCard("O backend nao retornou detalhamento por tipo de evento.")
        );
        return;
    }

    entries.forEach(([eventName, drivers]) => {
        const card = document.createElement("article");
        card.className = "event-breakdown-card";

        const title = document.createElement("h4");
        title.textContent = eventName;
        card.appendChild(title);

        if (!drivers.length) {
            card.appendChild(createPlainText("Nenhum motorista disponivel para este recorte."));
            refs.eventBreakdownGrid.appendChild(card);
            return;
        }

        const list = document.createElement("ul");
        list.className = "event-breakdown-list";

        drivers.forEach((driver) => {
            const item = document.createElement("li");

            const nameBlock = document.createElement("div");
            const name = document.createElement("strong");
            name.textContent = driver.Motorista;
            const history = document.createElement("span");
            history.textContent = `${formatCompact(driver.VolumeHistorico)} registros historicos`;
            nameBlock.append(name, history);

            const values = document.createElement("div");
            values.textContent =
                `${formatPercent(driver.ParticipacaoNoEventoPercentual || driver.Probabilidade)} | ${formatDecimal(driver.EventosEsperados)} esperados`;

            item.append(nameBlock, values);
            list.appendChild(item);
        });

        card.appendChild(list);
        refs.eventBreakdownGrid.appendChild(card);
    });
}


function setLoading(isLoading) {
    refs.fetchDataButton.disabled = isLoading;
    refs.fetchDataButton.textContent = isLoading ? "Atualizando..." : "Atualizar painel";

    if (isLoading) {
        refs.loadingSection.classList.remove("hidden");
        refs.predictionResultsSection.classList.add("hidden");
    } else {
        refs.loadingSection.classList.add("hidden");
        if (state.prediction) {
            refs.predictionResultsSection.classList.remove("hidden");
        }
    }
}


function setSystemStatus(message) {
    refs.systemStatusLabel.textContent = message;
}


function clearError() {
    refs.errorDisplaySection.classList.add("hidden");
    refs.errorMessage.textContent = "";
    refs.errorDetails.textContent = "";
}


function handleError(error) {
    const payload = error?.payload || null;
    const status = error?.status || null;

    let message = error?.message || "Nao foi possivel montar o painel preditivo.";
    let details = "Confira a conectividade com o backend ou escolha outra data.";

    if (payload?.error) {
        message = payload.error;
    }

    if (status === 404 && payload?.forecast_period_start && payload?.forecast_period_end) {
        details =
            `A data escolhida esta fora da janela prevista. Use um intervalo entre ${formatDate(payload.forecast_period_start)} e ${formatDate(payload.forecast_period_end)}.`;
        refs.predictionDateInput.value = payload.forecast_period_start;
    } else if (status === 400) {
        details = "A API espera datas no formato YYYY-MM-DD.";
    } else if (payload?.forecast_period_start && payload?.forecast_period_end) {
        details =
            `Janela atual de previsao: ${formatDate(payload.forecast_period_start)} ate ${formatDate(payload.forecast_period_end)}.`;
    } else if (payload?.requested_date) {
        details = `Data solicitada: ${payload.requested_date}.`;
    } else if (error?.details) {
        details = error.details;
    }

    refs.errorMessage.textContent = message;
    refs.errorDetails.textContent = details;
    refs.errorDisplaySection.classList.remove("hidden");
    refs.predictionResultsSection.classList.add("hidden");
    setSystemStatus("Falha ao sincronizar o painel");
}


function createEmptyListItem(message) {
    const item = document.createElement("li");
    item.textContent = message;
    return item;
}


function createEmptyCard(message) {
    const card = document.createElement("article");
    card.className = "stack-item";
    card.textContent = message;
    return card;
}


function createPlainText(message) {
    const text = document.createElement("p");
    text.className = "stack-item-subtitle";
    text.textContent = message;
    return text;
}


function parseIsoDate(value) {
    if (!value) {
        return null;
    }

    const [year, month, day] = value.split("-").map(Number);
    return new Date(year, month - 1, day);
}


function addDays(dateValue, amount) {
    const date = new Date(dateValue);
    date.setDate(date.getDate() + amount);
    return date;
}


function formatDate(value) {
    const date = parseIsoDate(value);
    return date ? dateFormatter.format(date) : "Nao informado";
}


function formatInputDate(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
}


function shortDateLabel(value) {
    const date = parseIsoDate(value);
    if (!date) {
        return "--";
    }

    return `${String(date.getDate()).padStart(2, "0")}/${String(date.getMonth() + 1).padStart(2, "0")}`;
}


function formatDecimal(value) {
    const numericValue = Number(value);
    return Number.isFinite(numericValue) ? numberFormatter.format(numericValue) : "N/A";
}


function formatCompact(value) {
    const numericValue = Number(value);
    return Number.isFinite(numericValue) ? compactFormatter.format(numericValue) : "N/A";
}


function formatPercent(value) {
    const numericValue = Number(value);
    return Number.isFinite(numericValue) ? `${numberFormatter.format(numericValue)}%` : "N/A";
}


function formatSignedPercent(value) {
    const numericValue = Number(value);
    if (!Number.isFinite(numericValue)) {
        return "N/A";
    }

    return `${numericValue > 0 ? "+" : ""}${numberFormatter.format(numericValue)}%`;
}


function formatRisk(level) {
    switch (level) {
        case "alto":
            return "Risco alto";
        case "moderado":
            return "Risco moderado";
        case "controlado":
            return "Risco controlado";
        default:
            return "Em analise";
    }
}
