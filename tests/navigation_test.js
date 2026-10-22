// No browser dependencies: exercise the actual tab handler with a minimal DOM.
// Run: node tests/navigation_test.js
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const html = fs.readFileSync(path.join(__dirname, '../templates/index.html'), 'utf8');
const source = html.slice(html.indexOf('function showTranspilationReport(view)'),
    html.indexOf('// Show the selected transpiled circuit analysis.'));
const names = ['original', 'analysis', 'verification', 'comparison'];
const elements = {};
let handler, focused;
const context = {document: {getElementById(id) { return elements[id] || null; }}};
vm.createContext(context);
const tabs = names.map(name => {
    const tab = {
        classList: {toggle(key, value) { this[key] = value; }},
        setAttribute(key, value) { this[key] = value; },
        click() { context.showTranspilationReport(name); },
        focus() { focused = name; }
    };
    elements[`report-${name}-tab`] = tab;
    elements[`report-${name}-panel`] = {hidden: name !== 'analysis'};
    return tab;
});
elements['transpilation-report-tabs'] = {
    addEventListener(event, fn) { assert.equal(event, 'keydown'); handler = fn; },
    querySelectorAll() { return tabs; }
};
vm.runInContext(source, context);
for (const selected of names) {
    context.showTranspilationReport(selected);
    for (const name of names) {
        assert.equal(elements[`report-${name}-panel`].hidden, name !== selected);
        assert.equal(elements[`report-${name}-tab`]['aria-selected'], String(name === selected));
        assert.equal(elements[`report-${name}-tab`].tabIndex, name === selected ? 0 : -1);
    }
}
for (const [key, start, expected] of [
    ['ArrowRight', 3, 'original'], ['ArrowLeft', 0, 'comparison'],
    ['Home', 2, 'original'], ['End', 0, 'comparison']
]) {
    let prevented = false;
    handler({key, target: tabs[start], preventDefault() { prevented = true; }});
    assert.ok(prevented);
    assert.equal(focused, expected);
    assert.equal(elements[`report-${expected}-panel`].hidden, false);
}
// Older responses without verification tabs must not break initial script execution.
vm.runInNewContext(source, {document: {getElementById() { return null; }}});
console.log('PASS: four views, selected states, focus, arrow/Home/End keys, and missing-tab fallback.');

// Basis selection must survive choosing an optimization level, and switching
// custom controls must not submit a circuit until the user applies settings.
const settingsElements = {
    'transpile-basis-control': {value: 'custom'},
    'transpile-level-control': {value: '0'},
    'custom-basis-fields': {hidden: true}
};
let submitted = 0;
const settingsContext = {
    document: {
        getElementById(id) { return settingsElements[id] || null; },
        querySelector() { return null; }
    },
    setActiveFormAction(action) { assert.equal(action, 'transpile'); },
    getActiveInputForm() { return {requestSubmit() { submitted++; }}; }
};
vm.createContext(settingsContext);
vm.runInContext(html.slice(html.indexOf('function beginTranspilation(level)'),
    html.indexOf('// Switch already-rendered reports')), settingsContext);
settingsContext.updateCustomBasisInput();
assert.equal(settingsElements['custom-basis-fields'].hidden, false);
assert.equal(submitted, 0);
settingsContext.beginTranspilation(2);
assert.equal(settingsElements['transpile-basis-control'].value, 'custom');
assert.equal(settingsElements['transpile-level-control'].value, '2');
assert.equal(submitted, 1);
settingsContext.selectTranspilationView('u_cx');
assert.equal(settingsElements['transpile-basis-control'].value, 'u_cx');
assert.equal(submitted, 2);
settingsContext.updateCustomBasisInput();
assert.equal(settingsElements['custom-basis-fields'].hidden, true);
console.log('PASS: custom controls, explicit submission, and basis/optimization selection preservation.');
