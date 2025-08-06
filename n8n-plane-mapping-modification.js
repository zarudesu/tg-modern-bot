// Добавить эту функцию в начало вашего n8n кода (после функции cleanHtml)

// Функция маппинга пользователей Plane на Telegram упоминания
function mapPlaneUserToMention(fullName) {
  const mapping = {
    // Дмитрий Гусев
    'Dmitriy Gusev': '@strikerstr',
    'Dmitry Gusev': '@strikerstr', 
    'Dima Gusev': '@strikerstr',
    'Гусев Дмитрий': '@strikerstr',
    
    // Тимофей Батырев
    'Тимофей Батырев': '@spiritphoto',
    'Timofeij Batyrev': '@spiritphoto',
    'Timofey Batyrev': '@spiritphoto',
    
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

// ИЗМЕНИТЬ функцию getAssigneesList (заменить существующую):
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
    
    // НОВОЕ: Преобразуем в упоминание
    return mapPlaneUserToMention(fullName);
    
  }).filter(name => name);
  
  return names.length > 0 ? names.join(', ') : `назначено: ${assignees.length} чел.`;
}

// ИЗМЕНИТЬ функцию getUserNameById (заменить существующую):
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
    
    // НОВОЕ: Преобразуем в упоминание
    return mapPlaneUserToMention(fullName);
  }
  return null;
}