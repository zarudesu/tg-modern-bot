// Получаем данные из предыдущих узлов
const webhookData = $node["Parse Webhook"].json;
const issue = $node["Get Issue Details"].json;
const project = $node["Get Project Details"].json;
const projectStates = $node["Get Project States"].json;

// Функция экранирования MarkdownV2
function escapeMarkdown(text) {
  if (!text) return '';
  return text.toString()
    .replace(/([_*\[\]()~`>#+=|{}.!\\-])/g, '\\$1');
}

// Функция очистки HTML
function cleanHtml(html) {
  if (!html) return '';
  return html
    .replace(/<[^>]*>/g, '')
    .replace(/&nbsp;/g, ' ')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&amp;/g, '&')
    .replace(/\r\n/g, '\n')
    .replace(/\r/g, '\n')
    .trim();
}

// Функция маппинга пользователей Plane на Telegram упоминания
function mapPlaneUserToMention(fullName) {
  const mapping = {
    // Дмитрий Гусев
    'Dmitriy Gusev': '@strikerstr',
    'Dmitry Gusev': '@strikerstr', 
    'Dima Gusev': '@strikerstr',
    'Гусев Дмитрий': '@strikerstr',
    'Дмитрий Гусев': '@strikerstr',
    
    // Тимофей Батырев
    'Тимофей Батырев': '@spiritphoto',
    'Timofeij Batyrev': '@spiritphoto',
    'Timofey Batyrev': '@spiritphoto',
    'Батырев Тимофей': '@spiritphoto',
    
    // Константин Макейкин
    'Konstantin Makeykin': '@your-username',
    'Kostya Makeykin': '@your-username', 
    'Константин Макейкин': '@your-username',
    'Макейкин Константин': '@your-username'
  };
  
  // Прямое соответствие
  if (mapping[fullName]) {
    return mapping[fullName];
  }
  
  // Поиск по частичному совпадению (фамилия или имя)
  const nameLower = fullName.toLowerCase();
  for (const [planeName, mention] of Object.entries(mapping)) {
    if (nameLower.includes('gusev') || nameLower.includes('гусев') || nameLower.includes('dmitr')) {
      return '@strikerstr';
    }
    if (nameLower.includes('batyrev') || nameLower.includes('батырев') || nameLower.includes('timof')) {
      return '@spiritphoto';
    }
    if (nameLower.includes('makeykin') || nameLower.includes('макейкин') || nameLower.includes('konst')) {
      return '@your-username';
    }
  }
  
  // Если не нашли, возвращаем оригинальное имя курсивом
  return `_${fullName}_`;
}

// Функция получения списка исполнителей (с упоминаниями)
function getAssigneesList(assignees) {
  if (!assignees || !Array.isArray(assignees) || assignees.length === 0) {
    return 'не назначены';
  }
  
  const names = assignees.map(a => {
    // Получаем полное имя
    let fullName = '';
    if (a.first_name && a.last_name) {
      fullName = `${a.first_name} ${a.last_name}`;
    } else {
      fullName = a.display_name || a.first_name || a.email || 'Неизвестный';
    }
    
    // Преобразуем в упоминание
    return mapPlaneUserToMention(fullName);
    
  }).filter(name => name);
  
  return names.length > 0 ? names.join(', ') : `назначено: ${assignees.length} чел.`;
}

// Функция получения имени пользователя по ID (с упоминаниями)
function getUserNameById(userId, assignees) {
  if (!assignees || !Array.isArray(assignees) || !userId) {
    return null;
  }
  
  const user = assignees.find(a => a.id === userId);
  if (user) {
    let fullName = '';
    if (user.first_name && user.last_name) {
      fullName = `${user.first_name} ${user.last_name}`;
    } else {
      fullName = user.display_name || user.first_name || user.email || 'Неизвестный';
    }
    
    // Преобразуем в упоминание
    return mapPlaneUserToMention(fullName);
  }
  return null;
}

// Функция получения названия статуса по ID
function getStateNameById(stateId, statesData) {
  if (!statesData || !stateId) {
    return null;
  }
  
  // Извлекаем массив статусов из results
  const states = statesData.results || [];
  
  if (!Array.isArray(states)) {
    return null;
  }
  
  const state = states.find(s => s.id === stateId);
  return state ? state.name : null;
}

// Функция обработки изменений в исполнителях
function formatAssigneeChange(oldValue, newValue, assignees) {
  const oldStr = oldValue ? String(oldValue) : '';
  const newStr = newValue ? String(newValue) : '';
  
  if (!oldStr && !newStr) return 'не указано';
  
  const oldIds = oldStr ? oldStr.split(',').filter(id => id.trim()) : [];
  const newIds = newStr ? newStr.split(',').filter(id => id.trim()) : [];
  
  const added = newIds.filter(id => !oldIds.includes(id));
  const removed = oldIds.filter(id => !newIds.includes(id));
  
  let changeText = '';
  
  if (added.length > 0) {
    const addedNames = added.map(id => getUserNameById(id, assignees)).filter(name => name);
    if (addedNames.length > 0) {
      changeText += `\\+ ${addedNames.join(', ')}`;
    } else {
      changeText += `\\+${added.length} назначен${added.length > 1 ? 'о' : ''}`;
    }
  }
  
  if (removed.length > 0) {
    if (changeText) changeText += ' ';
    const removedNames = removed.map(id => getUserNameById(id, assignees)).filter(name => name);
    if (removedNames.length > 0) {
      changeText += `\\- ${removedNames.join(', ')}`;
    } else {
      changeText += `\\-${removed.length} удален${removed.length > 1 ? 'о' : ''}`;
    }
  }
  
  return changeText || 'изменены';
}

// Функция обработки изменения полей
function formatFieldChange(field, oldValue, newValue, issue, states) {
  const oldStr = oldValue ? String(oldValue) : '';
  const newStr = newValue ? String(newValue) : '';
  
  if (field === 'assignee_ids') {
    return formatAssigneeChange(oldStr, newStr, issue.assignees);
  } else if (field === 'state_id' || field === 'state') {
    // Обработка статусов
    const oldStateName = getStateNameById(oldStr, states) || oldStr || 'неизвестный';
    const newStateName = getStateNameById(newStr, states) || newStr || 'неизвестный';
    return `${oldStateName} → ${newStateName}`;
  } else if (field === 'parent_id') {
    // Обработка родительской задачи (упрощенно)
    if (!oldStr && newStr) {
      return 'нет связи → установлена родительская задача';
    } else if (oldStr && !newStr) {
      return 'удалена родительская задача → нет связи';
    } else if (oldStr && newStr) {
      return 'изменена родительская задача';
    } else {
      return 'нет изменений';
    }
  } else if (field === 'priority') {
    // Обработка приоритета
    const oldPriority = priorityMap[oldStr.toLowerCase()] || oldStr || 'не указан';
    const newPriority = priorityMap[newStr.toLowerCase()] || newStr || 'не указан';
    return `${oldPriority} → ${newPriority}`;
  } else if (field === 'target_date') {
    // Обработка дат
    const oldDate = oldStr ? formatDate(oldStr) : 'не указана';
    const newDate = newStr ? formatDate(newStr) : 'не указана';
    return `${oldDate} → ${newDate}`;
  } else {
    // Обычная обработка
    return `${oldStr || 'пусто'} → ${newStr || 'пусто'}`;
  }
}

// Карты переводов
const priorityMap = {
  urgent: '🔥 Срочный',
  high: '⚠️ Высокий', 
  medium: '📍 Средний',
  low: '📝 Низкий',
  none: '⚪ Без приоритета'
};

const actionMap = {
  created: 'создана',
  updated: 'обновлена',
  deleted: 'удалена',
  commented: 'прокомментирована'
};

const eventEmojis = {
  created: '🆕',
  updated: '📝', 
  deleted: '🗑️',
  commented: '💬',
  assigned: '👤',
  state_changed: '🔄'
};

const fieldTranslations = {
  'assignee_ids': 'Исполнители',
  'state': 'Статус',
  'state_id': 'Статус',
  'priority': 'Приоритет',
  'target_date': 'Срок выполнения',
  'name': 'Название',
  'description': 'Описание',
  'parent_id': 'Родительская задача'
};

// Форматирование даты
function formatDate(value) {
  if (!value) return '—';
  const d = new Date(value);
  return `${d.getDate().toString().padStart(2, '0')}.${(d.getMonth() + 1).toString().padStart(2, '0')}.${d.getFullYear()} ${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`;
}

// Начинаем формировать сообщение
let text = '';

// Информация о событии из webhook
if (webhookData && webhookData.event) {
  if (webhookData.event === 'issue_comment') {
    // Это комментарий
    text += `💬 Добавлен комментарий\n\n`;
  } else if (webhookData.event === 'issue' && webhookData.action === 'created') {
    // Это создание задачи
    text += `🆕 Задача создана\n\n`;
  } else if (webhookData.event === 'issue' && webhookData.action === 'updated') {
    // Это обновление задачи
    text += `📝 Задача обновлена\n\n`;
  } else {
    // Остальные события
    const action = actionMap[webhookData.action] || webhookData.action;
    const eventEmoji = eventEmojis[webhookData.action] || '📦';
    text += `${eventEmoji} Задача ${escapeMarkdown(action)}\n\n`;
  }
}

// Обработка комментария
if (webhookData && webhookData.comment_html && webhookData.comment_html.trim()) {
  const commentText = cleanHtml(webhookData.comment_html);
  const shortComment = commentText.length > 150 ? commentText.slice(0, 150) + '\\.\\.\\.' : commentText;
  text += `*Комментарий:* ${escapeMarkdown(shortComment)}\n\n`;
}

// Обработка изменения полей
if (webhookData && webhookData.field) {
  const fieldName = fieldTranslations[webhookData.field] || webhookData.field;
  
  const changeDescription = formatFieldChange(
    webhookData.field, 
    webhookData.old_value, 
    webhookData.new_value, 
    issue, 
    projectStates
  );
  
  // Выбираем эмодзи в зависимости от типа изменения
  let emoji = '🔄';
  if (webhookData.field === 'assignee_ids') emoji = '👥';
  else if (webhookData.field === 'state_id' || webhookData.field === 'state') emoji = '📊';
  else if (webhookData.field === 'priority') emoji = '⚠️';
  else if (webhookData.field === 'target_date') emoji = '⏰';
  else if (webhookData.field === 'parent_id') emoji = '🔗';
  
  text += `${emoji} *${escapeMarkdown(fieldName)}:* ${escapeMarkdown(changeDescription)}\n\n`;
}

// Основная информация о задаче в карточном стиле
if (issue) {
  const projectIdentifier = project?.identifier || 'HHIVP';
  const taskNumber = `${projectIdentifier}\\-${issue.sequence_id}`;
  const title = escapeMarkdown(issue.name || 'Без названия');
  const priority = priorityMap[(issue.priority || '').toLowerCase()] || '⚪ Без приоритета';
  const createdDate = formatDate(issue.created_at);
  
  text += `╭─ 🎯 *${taskNumber}*\n`;
  text += `├ 📝 ${title}\n`;
  
  // Проект
  if (project && project.name) {
    text += `├ 📁 ${escapeMarkdown(project.name)}\n`;
  }
  
  text += `├ ${priority}\n`;
  text += `├ 📅 ${escapeMarkdown(createdDate)}\n`;
  
  // Исполнители с упоминаниями (ИЗМЕНЕНО!)
  const assigneesList = getAssigneesList(issue.assignees);
  text += `├ 👥 ${assigneesList}\n`;  // Убрали escapeMarkdown для упоминаний
  
  // Статус (с названием вместо ID)
  if (issue.state && issue.state.name) {
    text += `├ 📊 ${escapeMarkdown(issue.state.name)}\n`;
  } else if (issue.state) {
    // Если нет названия в объекте state, ищем по ID в projectStates
    const stateName = getStateNameById(issue.state, projectStates);
    text += `├ 📊 ${escapeMarkdown(stateName || 'не указан')}\n`;
  } else {
    text += `├ 📊 не указан\n`;
  }
  
  // Описание
  if (issue.description_html) {
    const description = cleanHtml(issue.description_html);
    if (description && description.length <= 100) {
      text += `├ 💭 ${escapeMarkdown(description)}\n`;
    } else if (description && description.length > 100) {
      const shortDesc = description.slice(0, 100) + '...';
      text += `├ 💭 ${escapeMarkdown(shortDesc)}\n`;
    }
  }
  
  // Сроки
  if (issue.target_date) {
    text += `├ ⏳ ${escapeMarkdown(formatDate(issue.target_date))}\n`;
  }
  
  // Ссылка
  const projectId = webhookData?.project_id || issue?.project;
  const issueId = webhookData?.issue_id || issue?.id;
  
  if (projectId && issueId) {
    const link = `https://plane.hhivp.com/hhivp/projects/${projectId}/issues/${issueId}`;
    text += `╰─ 🔗 [Открыть в Plane](${link})\n`;
  }
  
  text += `\n`;
}

// Разделитель в конце
text += `━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`;

// Возвращаем результат
return {
  chat_id: "YOUR_GROUP_CHAT_ID", 
  message_thread_id: "2231",
  text: text,
  parse_mode: "MarkdownV2",
  disable_web_page_preview: true
};