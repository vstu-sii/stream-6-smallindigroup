const requiredColumns = ["platform", "product_id", "review_id", "rating", "text"];
const platforms = new Set(["wildberries", "ozon", "yandex_market"]);

function parseCsv(source) {
  const rows = [];
  let fields = [];
  let field = "";
  let state = "unquoted";
  let line = 1;
  let rowLine = 1;

  function finishRow() {
    if (state === "closed" || fields.length || field) {
      rows.push({ line: rowLine, fields: [...fields, field] });
    }
    fields = [];
    field = "";
    state = "unquoted";
  }

  const text = source.replace(/^\uFEFF/, "").replace(/\r\n?/g, "\n");
  for (const character of text) {
    if (state === "quoted") {
      if (character === '"') {
        state = "closed";
      } else {
        field += character;
        if (character === "\n") line += 1;
      }
      continue;
    }
    if (character === "\n") {
      finishRow();
      line += 1;
      rowLine = line;
    } else if (character === ",") {
      fields.push(field);
      field = "";
      state = "unquoted";
    } else if (character === '"' && (state === "closed" || !field)) {
      if (state === "closed") field += '"';
      state = "quoted";
    } else if (state === "closed" || character === '"') {
      throw new Error(`Строка ${line}: проверьте кавычки в CSV.`);
    } else {
      field += character;
    }
  }
  if (state === "quoted") {
    throw new Error(`Строка ${rowLine}: незакрытая кавычка в CSV.`);
  }
  finishRow();
  return rows;
}

function validDate(value) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || value.startsWith("0000-")) return false;
  const date = new Date(value);
  return !Number.isNaN(date.valueOf()) && date.toISOString().slice(0, 10) === value;
}

function validateCsv(source) {
  const [header, ...rows] = parseCsv(source);
  if (!header) throw new Error("Файл пуст. Добавьте строку заголовков и отзывы.");
  const columns = header.fields.map((field) => field.trim());
  if (new Set(columns).size !== columns.length || columns.includes("")) {
    throw new Error("У каждого столбца должно быть уникальное непустое имя.");
  }
  const missing = requiredColumns.filter((column) => !columns.includes(column));
  if (missing.length) throw new Error(`Добавьте столбцы: ${missing.join(", ")}.`);
  if (!rows.length) throw new Error("Добавьте хотя бы один отзыв.");
  if (rows.length > 100) throw new Error(`В файле ${rows.length} строк с данными. Максимум — 100.`);

  const seen = new Set();
  const errors = [];
  let accepted = 0;
  for (const row of rows) {
    const issues = [];
    if (row.fields.length !== columns.length) {
      issues.push("число полей отличается от заголовка");
    } else {
      const review = Object.fromEntries(columns.map((name, index) => [name, row.fields[index].trim()]));
      const key = JSON.stringify([review.platform, review.review_id]);
      if (!platforms.has(review.platform)) issues.push("неизвестная площадка");
      if (!review.product_id) issues.push("пустой product_id");
      if (!review.review_id) issues.push("пустой review_id");
      if (!/^[1-5]$/.test(review.rating)) issues.push("оценка должна быть целым числом от 1 до 5");
      if (!review.text) issues.push("пустой текст");
      if (review.date && !validDate(review.date)) issues.push("проверьте дату в формате ГГГГ-ММ-ДД");
      if (seen.has(key)) issues.push("повтор review_id на той же площадке");
      if (!issues.length) seen.add(key);
    }
    if (issues.length) {
      errors.push(`Строка ${row.line}: ${issues.join("; ")}.`);
    } else {
      accepted += 1;
    }
  }
  return { accepted, errors };
}
