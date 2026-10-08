'use strict';

const fs = require('node:fs');
const vm = require('node:vm');


function plainObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}


async function main() {
  const codePath = process.argv[2];
  const inputPath = process.argv[3];
  if (!codePath || !inputPath) throw new Error('usage: node run_code_node.js CODE INPUT_JSON');

  const code = fs.readFileSync(codePath, 'utf8');
  const items = JSON.parse(fs.readFileSync(inputPath, 'utf8'));
  if (!Array.isArray(items)) throw new Error('runner input must be an array of n8n items');

  const clone = (value) => JSON.parse(JSON.stringify(value));
  const quietConsole = Object.freeze({log() {}, info() {}, warn() {}, error() {}});
  const sandbox = {
    $input: Object.freeze({
      all: () => clone(items),
      first: () => clone(items[0]),
      item: undefined,
    }),
    console: quietConsole,
    Buffer,
    URL,
    URLSearchParams,
  };
  const context = vm.createContext(sandbox, {name: 'n8n-code-node-offline'});
  const wrapped = `(async function () {\n${code}\n}).call(Object.freeze({}))`;
  const script = new vm.Script(wrapped, {filename: codePath});
  let result = script.runInContext(context, {timeout: 3000});
  result = await result;

  if (plainObject(result)) result = [result];
  if (!Array.isArray(result)) throw new Error('Code node must return an item array or an auto-wrappable object');

  const normalized = result.map((item, index) => {
    if (!plainObject(item)) throw new Error(`returned item ${index} is not an object`);
    if (Object.prototype.hasOwnProperty.call(item, 'json')) {
      if (!plainObject(item.json)) throw new Error(`returned item ${index}.json is not an object`);
      return item;
    }
    return {json: item};
  });

  process.stdout.write(JSON.stringify(normalized));
}


main().catch((error) => {
  process.stderr.write(`${error.name}: ${error.message}\n`);
  process.exitCode = 1;
});
