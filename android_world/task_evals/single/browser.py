# Copyright 2025 The android_world Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tasks that require interacting with a browser."""

import os
import hashlib
import random
import re
import time
from typing import Any
from android_world.env import adb_utils
from android_world.env import device_constants
from android_world.env import interface
from android_world.env import representation_utils
from android_world.task_evals import task_eval
from android_world.task_evals.utils import user_data_generation
from android_world.utils import datetime_utils
from android_world.utils import file_utils


class BrowserTask(task_eval.TaskEval):
  """Base class for browser tasks."""

  app_names = ['chrome']
  complexity = 2
  schema = {
      'type': 'object',
      'properties': {
          'browser_task_seed': {'type': 'number'},
      },
      'required': ['browser_task_seed'],
  }
  template = ''
  HTML = ''  # Implementation overrides.

  preamble = (
      'Open the file task.html in Downloads in the file manager; when prompted'
      ' open it with Chrome.'
  )

  def initialize_device_time(self, env: interface.AsyncEnv) -> None:
    """Initializes the device time."""
    datetime_utils.toggle_auto_settings(
        env.controller, datetime_utils.Toggle.ON
    )
    time.sleep(1.0)

  def initialize_task(self, env: interface.AsyncEnv):
    super().initialize_task(env)
    user_data_generation.clear_device_storage(env)
    chrome_activity = adb_utils.extract_package_name(
        adb_utils.get_adb_activity('chrome')
    )

    adb_utils.clear_app_data(
        chrome_activity,
        env.controller,
    )
    adb_utils.grant_permissions(
        chrome_activity,
        'android.permission.POST_NOTIFICATIONS',
        env.controller,
    )

    html = self.HTML.replace('%%SEED%%', str(self.params['browser_task_seed']))
    task_html_path = file_utils.convert_to_posix_path(
        file_utils.get_local_tmp_directory(), 'task.html'
    )
    with open(task_html_path, 'w', encoding='utf-8') as f:
      f.write(html)
    file_utils.copy_data_to_device(
        task_html_path,
        file_utils.convert_to_posix_path(
            device_constants.DOWNLOAD_DATA, 'task.html'
        ),
        env.controller,
    )

  def tear_down(self, env: interface.AsyncEnv):
    super().tear_down(env)
    user_data_generation.clear_device_storage(env)
    adb_utils.clear_app_data(
        adb_utils.extract_package_name(adb_utils.get_adb_activity('chrome')),
        env.controller,
    )
    datetime_utils.toggle_auto_settings(
        env.controller, datetime_utils.Toggle.OFF
    )

  def is_successful(self, env: interface.AsyncEnv) -> float:
    state = env.get_state()
    package_name = adb_utils.extract_package_name(
        adb_utils.get_current_activity(env.controller)[0]
    )
    if package_name != 'com.android.chrome':
      return 0.0

    for element in state.ui_elements:
      if element.text and 'Success!' in element.text:
        return 1.0
    return 0.0

  @classmethod
  def generate_random_params(cls) -> dict[str, Any]:
    return {'browser_task_seed': random.randint(0, 2**32 - 1)}


class BrowserMaze(BrowserTask):
  """Task to create a maze game."""

  @property
  def goal(self) -> str:
    return (
        self.preamble
        + ' Then navigate the X to the bottom-right cell, by using the'
        ' direction buttons.'
    )

  HTML = """<!DOCTYPE html>
<html>
<head>
  <title>Maze Puzzle</title>
  <style>
    .row {
      display: flex;
    }

    .cell {
      width: 110px;
      height: 110px;
      border: 1px solid black;
      display: flex;
      justify-content: center;
      align-items: center;
      font-size: 56px;
    }

    .wall {
      background-color: black;
    }

    .character {
      color: black;
    }

    .goal {
      background-color: green;
    }

    .controls {
      margin-top: 10px;
    }

    .controls button {
      margin-right: 5px;
      padding: 15px 28px;
      font-size: 30px;
    }
  </style>
</head>
<body>

  <div id="maze"></div>

  <div class="controls">
    <button onclick="moveCharacter('up')">Up</button>
    <button onclick="moveCharacter('down')">Down</button>
    <button onclick="moveCharacter('left')">Left</button>
    <button onclick="moveCharacter('right')">Right</button>
  </div>

  <script>
    const mazeSize = 4;
    let mazeLayout = [];
    let characterPosition = { row: 0, col: 0 };

    class SeededRNG {
    constructor(seed) {
        this.seed = seed;
    }

    random() {
        const a = 1664525;
        const c = 1013904223;
        const m = 2 ** 32;

        this.seed = (a * this.seed + c) % m;
        return this.seed / m;
    }
    }

    rng = new SeededRNG(%%SEED%%)
    function generateMaze() {
      mazeLayout = [];
      for (let row = 0; row < mazeSize; row++) {
        const currentRow = [];
        for (let col = 0; col < mazeSize; col++) {
          currentRow.push('#');
        }
        mazeLayout.push(currentRow);
      }

      // Create a path from start to goal
      const stack = [{ row: 0, col: 0 }];
      const directions = [[-1, 0], [1, 0], [0, -1], [0, 1]];

      while (stack.length > 0) {
        const { row, col } = stack.pop();
        mazeLayout[row][col] = ' ';

        if (row === mazeSize - 1 && col === mazeSize - 1) {
          break;
        }

        // Shuffle the order of directions
        for (let i = directions.length - 1; i > 0; i--) {
          const j = Math.floor(rng.random() * (i + 1));
          [directions[i], directions[j]] = [directions[j], directions[i]];
        }

        for (const [dx, dy] of directions) {
          const newRow = row + dx;
          const newCol = col + dy;
          if (
            newRow >= 0 &&
            newRow < mazeSize &&
            newCol >= 0 &&
            newCol < mazeSize &&
            mazeLayout[newRow][newCol] === '#'
          ) {
            stack.push({ row: newRow, col: newCol });
          }
        }
      }

      mazeLayout[0][0] = ' ';
      mazeLayout[mazeSize - 1][mazeSize - 1] = '$';
      characterPosition = { row: 0, col: 0 };
    }

    function renderMaze() {
      const mazeElement = document.getElementById('maze');
      mazeElement.innerHTML = '';

      for (let row = 0; row < mazeLayout.length; row++) {
        const rowElement = document.createElement('div');
        rowElement.className = 'row';

        for (let col = 0; col < mazeLayout[row].length; col++) {
          const cellElement = document.createElement('div');
          cellElement.className = 'cell';

          if (mazeLayout[row][col] === '#') {
            cellElement.classList.add('wall');
          } else if (row === characterPosition.row && col === characterPosition.col) {
            cellElement.classList.add('character');
            cellElement.innerHTML = 'X';
          } else if (mazeLayout[row][col] === '$') {
            cellElement.classList.add('goal');
          }

          rowElement.appendChild(cellElement);
        }

        mazeElement.appendChild(rowElement);
      }
    }

    function moveCharacter(direction) {
      const newPosition = { ...characterPosition };

      switch (direction) {
        case 'up':
          newPosition.row--;
          break;
        case 'down':
          newPosition.row++;
          break;
        case 'left':
          newPosition.col--;
          break;
        case 'right':
          newPosition.col++;
          break;
      }

      if (isValidMove(newPosition)) {
        characterPosition = newPosition;
        renderMaze();
        checkGoalReached();
      }
    }

    function isValidMove(position) {
      const { row, col } = position;
      if (
        row < 0 ||
        row >= mazeLayout.length ||
        col < 0 ||
        col >= mazeLayout[row].length ||
        mazeLayout[row][col] === '#'
      ) {
        return false;
      }
      return true;
    }

    function checkGoalReached() {
      const { row, col } = characterPosition;
      if (mazeLayout[row][col] === '$') {
        document.body.innerHTML = '<h1>Success!</h1>';
      }
    }

    generateMaze();
    renderMaze();
  </script>
</body>
</html>"""


class BrowserMultiply(BrowserTask):
  """Task for multiplying multiple numbers together."""

  complexity = 2.2

  @property
  def goal(self) -> str:
    return (
        self.preamble
        + ' Then click the button 5 times, remember the numbers displayed, and'
        ' enter their product in the form.'
    )

  HTML = """<!DOCTYPE html>
<html>
<head>
  <title>Memory Task</title>
  <style>
    .container {
      text-align: center;
      margin-top: 50px;
    }

    .number {
      font-size: 48px;
      margin-bottom: 20px;
    }

    .button {
      padding: 10px 20px;
      font-size: 24px;
      margin-bottom: 20px;
    }

    .form {
      margin-top: 20px;
    }

    .form input {
      padding: 5px;
      font-size: 18px;
    }

    .form button {
      padding: 5px 10px;
      font-size: 18px;
    }
  </style>
</head>
<body>
  <div class="container">
    <div class="number" id="number"></div>
    <button class="button" id="button" onclick="handleButtonClick()">Click Me</button>
    <div class="form" id="form" style="display: none;">
      <input type="number" id="answer" placeholder="Enter the product">
      <button onclick="checkAnswer()">Submit</button>
    </div>
    <div id="result"></div>
  </div>

  <script>
    class SeededRNG {
      constructor(seed) {
        this.seed = seed;
      }

      random() {
        const a = 1664525;
        const c = 1013904223;
        const m = 2 ** 32;
        this.seed = (a * this.seed + c) % m;
        return this.seed / m;
      }
    }

    const rng = new SeededRNG(%%SEED%%);
    const numbers = [];
    let clickCount = 0;

    function generateNumber() {
      const number = Math.floor(rng.random() * 10) + 1;
      numbers.push(number);
      document.getElementById('number').textContent = number;
    }

    function handleButtonClick() {
      clickCount++;
      if (clickCount < 5) {
        generateNumber();
      } else {
        document.getElementById('button').style.display = 'none';
        document.getElementById('number').style.display = 'none';
        document.getElementById('form').style.display = 'block';
      }
    }

    function checkAnswer() {
      const answer = parseInt(document.getElementById('answer').value);
      const product = numbers.reduce((acc, num) => acc * num, 1);
      const result = document.getElementById('result');
      if (answer === product) {
        result.innerHTML = '<h2>Success!</h2>';
      } else {
        result.innerHTML = '<h2></h2>';
      }
    }

    generateNumber();
  </script>
</body>
</html>"""


class BrowserSudoku(BrowserTask):
  """Task for solving a 4*4 Sudoku puzzle."""

  complexity = 3.5

  @property
  def goal(self) -> str:
    return (
        self.preamble
        + ' Then solve the 4*4 Sudoku puzzle by filling in the empty cells.'
        ' Each row, column, and 2*2 box must contain the numbers 1-4.'
    )

  HTML = """<!DOCTYPE html>
<html>
<head>
  <title>4*4 Sudoku</title>
  <style>
    body {
      font-family: Arial, sans-serif;
      text-align: center;
      margin: 20px;
    }

    h1 {
      font-size: 32px;
      margin-bottom: 10px;
    }

    .instructions {
      font-size: 18px;
      margin-bottom: 20px;
      color: #555;
    }

    #sudoku-grid {
      display: inline-block;
      border: 3px solid #000;
      margin: 20px auto;
    }

    .sudoku-row {
      display: flex;
    }

    .sudoku-cell {
      width: 80px;
      height: 80px;
      border: 1px solid #999;
      display: flex;
      justify-content: center;
      align-items: center;
      font-size: 36px;
      font-weight: bold;
      user-select: none;
    }

    .sudoku-cell.prefilled {
      background-color: #e8e8e8;
      color: #000;
      cursor: default;
    }

    .sudoku-cell.empty {
      background-color: #fff;
      cursor: pointer;
    }

    .sudoku-cell.empty:hover {
      background-color: #f0f0f0;
    }

    .sudoku-cell.selected {
      background-color: #cce5ff;
    }

    /* Thicker borders for 2x2 boxes */
    .sudoku-row .sudoku-cell:nth-child(2) {
      border-right: 2px solid #000;
    }

    .sudoku-row:nth-child(2) .sudoku-cell {
      border-bottom: 2px solid #000;
    }

    .number-buttons {
      margin: 20px;
    }

    .number-buttons button {
      width: 60px;
      height: 60px;
      margin: 5px;
      font-size: 28px;
      font-weight: bold;
      background-color: #4CAF50;
      color: white;
      border: none;
      border-radius: 5px;
      cursor: pointer;
    }

    .number-buttons button:hover {
      background-color: #45a049;
    }

    .number-buttons button.clear {
      background-color: #f44336;
    }

    .number-buttons button.clear:hover {
      background-color: #da190b;
    }

    .control-buttons {
      margin: 20px;
    }

    .control-buttons button {
      padding: 15px 30px;
      margin: 5px;
      font-size: 20px;
      font-weight: bold;
      border: none;
      border-radius: 5px;
      cursor: pointer;
    }

    .submit-button {
      background-color: #2196F3;
      color: white;
    }

    .submit-button:hover {
      background-color: #0b7dda;
    }

    #message {
      font-size: 24px;
      margin-top: 20px;
      font-weight: bold;
    }
  </style>
</head>
<body>
  <h1>4×4 Sudoku</h1>
  <div class="instructions">
    Fill each row, column, and 2×2 box with numbers 1-4. No duplicate in any row, column, or box.
  </div>

  <div id="sudoku-grid"></div>

  <div class="number-buttons">
    <button onclick="placeNumber(1)">1</button>
    <button onclick="placeNumber(2)">2</button>
    <button onclick="placeNumber(3)">3</button>
    <button onclick="placeNumber(4)">4</button>
    <button class="clear" onclick="placeNumber(0)">Clear</button>
  </div>

  <div class="control-buttons">
    <button class="submit-button" onclick="checkSolution()">Submit</button>
  </div>

  <div id="message"></div>

  <script>
    class SeededRNG {
      constructor(seed) {
        this.seed = seed >>> 0;
      }

      random() {
        const a = 1664525;
        const c = 1013904223;
        const m = 2 ** 32;
        this.seed = (a * this.seed + c) % m;
        return this.seed / m;
      }
    }

    const rng = new SeededRNG(%%SEED%%);

    let solution = [];
    let puzzle = [];
    let grid = [];
    let prefilled = [];
    let selectedCell = null;

    // 检查在 board 的 (row,col) 放 num 是否冲突（用于解题/计数）
    function isValidInBoard(board, row, col, num) {
      for (let i = 0; i < 4; i++) {
        if (board[row][i] === num) return false;
        if (board[i][col] === num) return false;
      }
      const br = Math.floor(row / 2) * 2;
      const bc = Math.floor(col / 2) * 2;
      for (let r = br; r < br + 2; r++) {
        for (let c = bc; c < bc + 2; c++) {
          if (board[r][c] === num) return false;
        }
      }
      return true;
    }

    // 简单回溯求解（生成完整解）
    function solveBoard(board) {
      for (let r = 0; r < 4; r++) {
        for (let c = 0; c < 4; c++) {
          if (board[r][c] === 0) {
            const nums = [1,2,3,4];
            for (let i = nums.length - 1; i > 0; i--) {
              const j = Math.floor(rng.random() * (i + 1));
              [nums[i], nums[j]] = [nums[j], nums[i]];
            }
            for (const n of nums) {
              if (isValidInBoard(board, r, c, n)) {
                board[r][c] = n;
                if (solveBoard(board)) return true;
                board[r][c] = 0;
              }
            }
            return false;
          }
        }
      }
      return true;
    }

    // 生成完整解
    function generateFullSolution() {
      const b = [
        [0,0,0,0],
        [0,0,0,0],
        [0,0,0,0],
        [0,0,0,0]
      ];
      solveBoard(b);
      return b;
    }

    // 生成谜题（这里尽力移除指定数量的格子，但不强制唯一解）
    function generatePuzzle(removalsMin = 6, removalsMax = 8) {
      const full = generateFullSolution();
      const p = full.map(r => r.slice());
      const cellsToRemove = removalsMin + Math.floor(rng.random() * (removalsMax - removalsMin + 1));
      let removed = 0;
      const coords = [];
      for (let r = 0; r < 4; r++) for (let c = 0; c < 4; c++) coords.push([r,c]);
      // shuffle coords
      for (let i = coords.length - 1; i > 0; i--) {
        const j = Math.floor(rng.random() * (i + 1));
        [coords[i], coords[j]] = [coords[j], coords[i]];
      }
      for (const [r, c] of coords) {
        if (removed >= cellsToRemove) break;
        if (p[r][c] !== 0) {
          p[r][c] = 0;
          removed++;
        }
      }
      return { puzzle: p, solution: full };
    }

    // 验证玩家填写的 grid 是否满足数独约束（行/列/2x2 区域含 1..4 且无重复）
    function validateGrid(finalGrid) {
      // 所有格子必须为 1-4
      for (let r = 0; r < 4; r++) {
        for (let c = 0; c < 4; c++) {
          const v = finalGrid[r][c];
          if (![1,2,3,4].includes(v)) return { ok:false, reason: '所有格子必须填 1-4' };
        }
      }
      // 行
      for (let r = 0; r < 4; r++) {
        const seen = new Set();
        for (let c = 0; c < 4; c++) {
          const v = finalGrid[r][c];
          if (seen.has(v)) return { ok:false, reason: `第 ${r+1} 行有重复` };
          seen.add(v);
        }
      }
      // 列
      for (let c = 0; c < 4; c++) {
        const seen = new Set();
        for (let r = 0; r < 4; r++) {
          const v = finalGrid[r][c];
          if (seen.has(v)) return { ok:false, reason: `第 ${c+1} 列有重复` };
          seen.add(v);
        }
      }
      // 2x2 区域
      for (let br = 0; br < 2; br++) {
        for (let bc = 0; bc < 2; bc++) {
          const seen = new Set();
          for (let r = br*2; r < br*2+2; r++) {
            for (let c = bc*2; c < bc*2+2; c++) {
              const v = finalGrid[r][c];
              if (seen.has(v)) return { ok:false, reason: `某个 2x2 区域有重复` };
              seen.add(v);
            }
          }
        }
      }
      return { ok:true };
    }

    // 渲染
    function renderGrid() {
      const gridElement = document.getElementById('sudoku-grid');
      gridElement.innerHTML = '';

      for (let row = 0; row < 4; row++) {
        const rowElement = document.createElement('div');
        rowElement.className = 'sudoku-row';

        for (let col = 0; col < 4; col++) {
          const cellElement = document.createElement('div');
          cellElement.className = 'sudoku-cell';
          cellElement.dataset.row = row;
          cellElement.dataset.col = col;

          if (prefilled[row][col]) {
            cellElement.classList.add('prefilled');
            cellElement.textContent = puzzle[row][col];
          } else {
            cellElement.classList.add('empty');
            if (grid[row][col] !== 0) {
              cellElement.textContent = grid[row][col];
            }
            cellElement.addEventListener('click', () => selectCell(row, col));
          }

          rowElement.appendChild(cellElement);
        }

        gridElement.appendChild(rowElement);
      }

      if (selectedCell) {
        const {row, col} = selectedCell;
        if (!prefilled[row][col]) {
          const cellElement = document.querySelector(`.sudoku-cell[data-row="${row}"][data-col="${col}"]`);
          if (cellElement) cellElement.classList.add('selected');
        } else {
          selectedCell = null;
        }
      }
    }

    function selectCell(row, col) {
      if (prefilled[row][col]) return;
      document.querySelectorAll('.sudoku-cell').forEach(cell => cell.classList.remove('selected'));
      selectedCell = { row, col };
      const cellElement = document.querySelector(`.sudoku-cell[data-row="${row}"][data-col="${col}"]`);
      if (cellElement) cellElement.classList.add('selected');
    }

    function placeNumber(num) {
      if (!selectedCell) {
        const msgEl = document.getElementById('message');
        msgEl.textContent = 'Please select a cell first';
        setTimeout(() => { msgEl.textContent = ''; }, 1500);
        return;
      }
      const { row, col } = selectedCell;
      grid[row][col] = num;
      renderGrid();
      if (num !== 0) selectCell(row, col);
    }

    // 关键点：提交时只做约束验证（不和生成时的 solution 比较）
    function checkSolution() {
      // 先确保没有空格
      for (let r = 0; r < 4; r++) {
        for (let c = 0; c < 4; c++) {
          if (grid[r][c] === 0) {
            document.getElementById('message').textContent = '还有未填的格子';
            setTimeout(() => document.getElementById('message').textContent = '', 2000);
            return;
          }
        }
      }

      const res = validateGrid(grid);
      if (res.ok) {
        document.body.innerHTML = '<h1>Success!</h1>';
      } else {
        document.getElementById('message').textContent = '错误: ' + res.reason;
        setTimeout(() => document.getElementById('message').textContent = '', 2000);
      }
    }

    // 初始化
    function initGame() {
      const gen = generatePuzzle(6,8);
      puzzle = gen.puzzle;
      solution = gen.solution;
      prefilled = [];
      grid = [];
      for (let r = 0; r < 4; r++) {
        prefilled.push([]);
        grid.push([]);
        for (let c = 0; c < 4; c++) {
          prefilled[r].push(puzzle[r][c] !== 0);
          grid[r].push(puzzle[r][c]);
        }
      }
      selectedCell = null;
      renderGrid();
    }

    initGame();
  </script>
</body>
</html>
"""


class BrowserSlider(BrowserTask):
  """Task for positioning a slider to a target value."""

  @property
  def goal(self) -> str:
    return (
        self.preamble
        + ' Then drag the slider to match the target number shown at the top.'
    )

  HTML = """<!DOCTYPE html>
<html>
<head>
  <title>Slider Challenge</title>
  <style>
    body {
      font-family: Arial, sans-serif;
      text-align: center;
      margin: 50px;
      background-color: #f5f5f5;
    }

    h1 {
      font-size: 36px;
      margin-bottom: 10px;
      color: #333;
    }

    .instructions {
      font-size: 20px;
      margin-bottom: 30px;
      color: #666;
    }

    .target-display {
      font-size: 48px;
      font-weight: bold;
      margin: 30px 0;
      padding: 20px;
      background-color: #4CAF50;
      color: white;
      border-radius: 10px;
      display: inline-block;
      min-width: 200px;
    }

    .slider-container {
      margin: 50px auto;
      max-width: 600px;
      padding: 30px;
      background-color: white;
      border-radius: 10px;
      box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    }

    .slider-wrapper {
      position: relative;
      margin: 30px 0;
    }

    .slider {
      width: 100%;
      height: 20px;
      -webkit-appearance: none;
      appearance: none;
      background: linear-gradient(to right, #2196F3, #4CAF50, #FFC107, #FF5722);
      outline: none;
      border-radius: 10px;
      cursor: pointer;
    }

    .slider::-webkit-slider-thumb {
      -webkit-appearance: none;
      appearance: none;
      width: 40px;
      height: 40px;
      background: #333;
      cursor: pointer;
      border-radius: 50%;
      border: 3px solid white;
      box-shadow: 0 2px 5px rgba(0,0,0,0.3);
    }

    .slider::-moz-range-thumb {
      width: 40px;
      height: 40px;
      background: #333;
      cursor: pointer;
      border-radius: 50%;
      border: 3px solid white;
      box-shadow: 0 2px 5px rgba(0,0,0,0.3);
    }

    .value-display {
      font-size: 42px;
      font-weight: bold;
      margin: 20px 0;
      color: #333;
      padding: 15px;
      background-color: #f0f0f0;
      border-radius: 8px;
    }

    .scale {
      display: flex;
      justify-content: space-between;
      margin-top: 10px;
      font-size: 16px;
      color: #666;
    }

    .submit-button {
      margin-top: 30px;
      padding: 15px 40px;
      font-size: 22px;
      font-weight: bold;
      background-color: #2196F3;
      color: white;
      border: none;
      border-radius: 8px;
      cursor: pointer;
      transition: background-color 0.3s;
    }

    .submit-button:hover {
      background-color: #0b7dda;
    }

    .tolerance-hint {
      font-size: 14px;
      color: #999;
      margin-top: 10px;
    }
  </style>
</head>
<body>
  <h1>Slider Challenge</h1>
  <div class="instructions">Drag the slider to match the target number</div>

  <div class="target-display">
    Target: <span id="target">50</span>
  </div>

  <div class="slider-container">
    <div class="slider-wrapper">
      <input type="range" min="0" max="100" value="50" class="slider" id="slider">
      <div class="scale">
        <span>0</span>
        <span>25</span>
        <span>50</span>
        <span>75</span>
        <span>100</span>
      </div>
    </div>

    <div class="value-display">
      Current: <span id="current-value">50</span>
    </div>

    <button class="submit-button" onclick="checkValue()">Submit</button>
    <div class="tolerance-hint">Must match exactly!</div>
  </div>

  <script>
    class SeededRNG {
      constructor(seed) {
        this.seed = seed;
      }

      random() {
        const a = 1664525;
        const c = 1013904223;
        const m = 2 ** 32;
        this.seed = (a * this.seed + c) % m;
        return this.seed / m;
      }
    }

    const rng = new SeededRNG(%%SEED%%);
    
    // Generate target value between 10 and 90 (avoiding edges)
    const targetValue = Math.floor(rng.random() * 81) + 10;
    document.getElementById('target').textContent = targetValue;

    const slider = document.getElementById('slider');
    const currentValueDisplay = document.getElementById('current-value');

    // Set initial slider position to a random value away from target
    let initialValue;
    do {
      initialValue = Math.floor(rng.random() * 101);
    } while (Math.abs(initialValue - targetValue) < 15);
    
    slider.value = initialValue;
    currentValueDisplay.textContent = initialValue;

    // Update display when slider moves
    slider.addEventListener('input', function() {
      currentValueDisplay.textContent = this.value;
    });

    function checkValue() {
      const currentValue = parseInt(slider.value);

      if (currentValue === targetValue) {
        document.body.innerHTML = '<h1>Success!</h1>';
      } else {
        // Show a hint
        const difference = currentValue - targetValue;
        let hint = '';
        if (difference > 0) {
          hint = `Too high! (${currentValue} > ${targetValue})`;
        } else {
          hint = `Too low! (${currentValue} < ${targetValue})`;
        }
        
        // Flash hint briefly
        const hintDiv = document.createElement('div');
        hintDiv.style.cssText = 'position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%); background: rgba(0,0,0,0.8); color: white; padding: 20px 40px; border-radius: 10px; font-size: 24px; z-index: 1000;';
        hintDiv.textContent = hint;
        document.body.appendChild(hintDiv);
        
        setTimeout(() => {
          hintDiv.remove();
        }, 1500);
      }
    }
  </script>
</body>
</html>"""


class BrowserProgressBar(BrowserTask):
  """Task for waiting for a progress bar to complete before proceeding."""

  complexity = 1.8
  @property
  def goal(self) -> str:
    return (
        self.preamble
        + ' Then wait for the progress bar to reach 100% and click the'
        ' Continue button that appears.'
    )

  HTML = """<!DOCTYPE html>
<html>
<head>
  <title>Loading Progress</title>
  <style>
    body {
      font-family: Arial, sans-serif;
      text-align: center;
      margin: 50px;
      background-color: #f5f5f5;
    }

    h1 {
      font-size: 36px;
      margin-bottom: 20px;
      color: #333;
    }

    .loading-container {
      max-width: 600px;
      margin: 50px auto;
      padding: 40px;
      background-color: white;
      border-radius: 10px;
      box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    }

    .status-text {
      font-size: 24px;
      margin-bottom: 30px;
      color: #666;
    }

    .progress-container {
      width: 100%;
      height: 40px;
      background-color: #e0e0e0;
      border-radius: 20px;
      overflow: hidden;
      margin: 30px 0;
      position: relative;
    }

    .progress-bar {
      height: 100%;
      background: linear-gradient(90deg, #4CAF50, #8BC34A);
      border-radius: 20px;
      transition: width 0.3s ease;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .progress-text {
      position: absolute;
      width: 100%;
      text-align: center;
      line-height: 40px;
      font-size: 20px;
      font-weight: bold;
      color: #333;
      z-index: 1;
    }

    .continue-button {
      padding: 15px 40px;
      font-size: 22px;
      font-weight: bold;
      background-color: #2196F3;
      color: white;
      border: none;
      border-radius: 8px;
      cursor: pointer;
      margin-top: 30px;
      display: none;
    }

    .continue-button:hover {
      background-color: #0b7dda;
    }

    .spinner {
      border: 4px solid #f3f3f3;
      border-top: 4px solid #4CAF50;
      border-radius: 50%;
      width: 50px;
      height: 50px;
      animation: spin 1s linear infinite;
      margin: 20px auto;
      display: none; /* hidden until loading starts */
    }

    @keyframes spin {
      0% { transform: rotate(0deg); }
      100% { transform: rotate(360deg); }
    }

    .control-row {
      display: flex;
      justify-content: center;
      gap: 12px;
      margin-top: 12px;
    }

    .button {
      padding: 10px 18px;
      font-size: 16px;
      border-radius: 6px;
      cursor: pointer;
      border: none;
      background: #e0e0e0;
    }

    .button:hover { filter: brightness(0.95); }
    .start-btn { background:#4CAF50; color:#fff; }
    .abort-btn { background:#f44336; color:#fff; }
    .reset-btn { background:#ff9800; color:#fff; }
  </style>
</head>
<body>
  <h1>Loading Content</h1>
  
  <div class="loading-container">
    <div class="status-text" id="status">Click Start to begin.</div>
    <div class="spinner" id="spinner"></div>
    
    <div class="progress-container">
      <div class="progress-text" id="progress-text">0%</div>
      <div class="progress-bar" id="progress-bar" style="width: 0%"></div>
    </div>

    <button class="continue-button" id="continue-btn" onclick="handleContinue()">
      Continue
    </button>

    <div class="control-row">
      <button class="button start-btn" id="start-btn">Start</button>
      <button class="button abort-btn" id="abort-btn">Abort</button>
      <button class="button reset-btn" id="reset-btn">Reset</button>
    </div>
  </div>

  <script>
    class SeededRNG {
      constructor(seed) {
        this.seed = seed >>> 0;
      }

      random() {
        const a = 1664525;
        const c = 1013904223;
        const m = 2 ** 32;
        this.seed = (a * this.seed + c) % m;
        return this.seed / m;
      }
    }

    const rng = new SeededRNG(%%SEED%%);

    let currentProgress = 0;
    const progressBar = document.getElementById('progress-bar');
    const progressText = document.getElementById('progress-text');
    const continueBtn = document.getElementById('continue-btn');
    const statusText = document.getElementById('status');
    const spinner = document.getElementById('spinner');
    const abortBtn = document.getElementById('abort-btn');
    const resetBtn = document.getElementById('reset-btn');
    const startBtn = document.getElementById('start-btn');

    let animationFrameId = null;
    let startTime = null;
    let totalDuration = 60000; // 1 minute
    let loadingActive = false;

    function startProgress() {
      if (loadingActive) return;
      loadingActive = true;
      startTime = performance.now();
      currentProgress = 0;
      progressBar.style.width = '0%';
      progressText.textContent = '0%';
      continueBtn.style.display = 'none';
      spinner.style.display = 'block';
      statusText.textContent = 'Loading...';
      statusText.style.color = '#666';
      animationFrameId = requestAnimationFrame(updateProgressAnimationFrame);
    }

    function updateProgressAnimationFrame(timestamp) {
      if (!loadingActive) return;
      if (!startTime) startTime = timestamp;
      const elapsed = timestamp - startTime;

      if (elapsed < totalDuration) {
        currentProgress = (elapsed / totalDuration) * 100;
        const displayProgress = Math.floor(currentProgress);
        progressBar.style.width = displayProgress + '%';
        progressText.textContent = displayProgress + '%';
        animationFrameId = requestAnimationFrame(updateProgressAnimationFrame);
      } else {
        currentProgress = 100;
        progressBar.style.width = '100%';
        progressText.textContent = '100%';
        spinner.style.display = 'none';
        statusText.textContent = 'Loading complete!';
        statusText.style.color = '#4CAF50';
        loadingActive = false;
        continueBtn.style.display = 'inline-block';
      }
    }

    function abortProgress() {
      if (!loadingActive) {
        statusText.textContent = 'Loading aborted!';
        statusText.style.color = '#f44336';
        spinner.style.display = 'none';
        continueBtn.style.display = 'none';
        return;
      }
      cancelAnimationFrame(animationFrameId);
      loadingActive = false;
      spinner.style.display = 'none';
      continueBtn.style.display = 'none';
      statusText.textContent = 'Loading aborted!';
      statusText.style.color = '#f44336';
    }

    function resetProgress() {
      cancelAnimationFrame(animationFrameId);
      loadingActive = false;
      startTime = null;
      currentProgress = 0;
      progressBar.style.width = '0%';
      progressText.textContent = '0%';
      spinner.style.display = 'none';
      continueBtn.style.display = 'none';
      statusText.textContent = 'Click Start to begin.';
      statusText.style.color = '#666';
    }

    function handleContinue() {
      document.body.innerHTML = '<h1>Success!</h1>';
    }

    startBtn.addEventListener('click', startProgress);
    abortBtn.addEventListener('click', abortProgress);
    resetBtn.addEventListener('click', resetProgress);
  </script>
</body>
</html>"""


class BrowserPopupDismiss(BrowserTask):
  """Task for dismissing popup dialogs while completing a form."""

  complexity = 2.5
  schema = {
      "type": "object",
      "properties": {
          "name": {"type": "string"},
          "email": {"type": "string"},
          "country": {"type": "string"},
      },
      "required": ["name", "email", "country"],
  }
  template = (
      " Then fill in the form with following values and submit:\n"
      "Name: {name}, Email: {email}, Country: {country}."
  )

  @classmethod
  def generate_random_params(cls) -> dict[str, str]:
    name_email_pairs = [
        ("Alice Smith", "alice.smith@test.com"),
        ("Bob Johnson", "bob.j@test.com"),
        ("Charlie Brown", "charlie.b@test.com"),
        ("David Miller", "david.m@test.com"),
        ("Eve Davis", "eve.d@test.com"),
        ("Frank Garcia", "frank.g@test.com"),
        ("Grace Rodriguez", "grace.r@test.com"),
        ("Henry Martinez", "henry.m@test.com"),
        ("Ivy Hernandez", "ivy.h@test.com"),
        ("Jack Lopez", "jack.l@test.com"),
    ]
    countries = [
        "US", "Canada", "UK", "Australia",
        "Germany", "France", "Japan", "China", "India", "Brazil",
    ]

    name, email = random.choice(name_email_pairs)
    country = random.choice(countries)

    params = {
        "name": name,
        "email": email,
        "country": country,
        'browser_task_seed': random.randint(0, 2**32 - 1)
    }
    return params

  @property
  def goal(self) -> str:
    return self.preamble + self.template.format(**self.params)

  HTML = """<!DOCTYPE html>
<html>
<head>
  <title>Form with Popups</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    body {
      font-family: Arial, sans-serif;
      margin: 0;
      padding: 0;
      background-color: #f5f5f5;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
    }

    h1 {
      text-align: center;
      font-size: 28px;
      margin: 20px 0;
      color: #333;
    }

    .form-container {
      width: 90%;
      max-width: 500px;
      padding: 20px;
      background-color: white;
      border-radius: 10px;
      box-shadow: 0 2px 10px rgba(0,0,0,0.1);
      position: relative;
      z-index: 1;
      margin-bottom: 50px;
    }

    .form-group {
      margin-bottom: 15px;
    }

    label {
      display: block;
      margin-bottom: 5px;
      font-size: 16px;
      color: #333;
      font-weight: bold;
    }

    input[type="text"],
    input[type="email"],
    select {
      width: 100%;
      padding: 10px;
      font-size: 16px;
      border: 2px solid #ddd;
      border-radius: 5px;
      box-sizing: border-box;
    }

    input:focus, select:focus {
      border-color: #4CAF50;
      outline: none;
    }

    .submit-button {
      width: 100%;
      padding: 12px;
      font-size: 18px;
      font-weight: bold;
      background-color: #4CAF50;
      color: white;
      border: none;
      border-radius: 5px;
      cursor: pointer;
      margin-top: 10px;
    }

    .submit-button:hover {
      background-color: #45a049;
    }

    .popup-overlay {
      display: none;
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      z-index: 1000;
      pointer-events: none;
    }

    .popup {
      background-color: white;
      padding: 15px 20px;
      border-radius: 10px;
      box-shadow: 0 4px 20px rgba(0,0,0,0.3);
      max-width: 80%;
      text-align: center;
      position: absolute;
      pointer-events: auto;
    }

    .popup h2 {
      font-size: 20px;
      margin-bottom: 10px;
      color: #333;
    }

    .popup p {
      font-size: 14px;
      margin-bottom: 10px;
      color: #666;
    }

    .popup-close {
      padding: 6px 20px;
      font-size: 14px;
      font-weight: bold;
      background-color: #2196F3;
      color: white;
      border: none;
      border-radius: 5px;
      cursor: pointer;
    }

    .popup-close:hover {
      background-color: #0b7dda;
    }

    .close-x {
      position: absolute;
      top: 6px;
      right: 10px;
      font-size: 22px;
      font-weight: bold;
      color: #999;
      cursor: pointer;
      line-height: 20px;
    }

    .close-x:hover {
      color: #333;
    }

    #cookie-bar {
      display: none;
      position: fixed;
      bottom: 0;
      left: 0;
      width: 100%;
      background-color: #333;
      color: white;
      padding: 12px 15px;
      box-sizing: border-box;
      font-size: 14px;
      z-index: 2000;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    #cookie-bar button {
      background-color: #4CAF50;
      border: none;
      color: white;
      padding: 8px 15px;
      border-radius: 5px;
      font-size: 14px;
      cursor: pointer;
    }

    #cookie-bar button:hover {
      background-color: #45a049;
    }
  </style>
</head>
<body>
  <h1>Registration Form</h1>
  
  <div class="form-container">
    <form id="main-form">
      <div class="form-group">
        <label for="name">Full Name:</label>
        <input type="text" id="name" name="name" required>
      </div>

      <div class="form-group">
        <label for="email">Email Address:</label>
        <input type="email" id="email" name="email" required>
      </div>

      <div class="form-group">
        <label for="country">Country:</label>
        <select id="country" name="country" required>
          <option value="">Select a country</option>
          <option value="US">US</option>
          <option value="Canada">Canada</option>
          <option value="UK">UK</option>
          <option value="Australia">Australia</option>
          <option value="Germany">Germany</option>
          <option value="France">France</option>
          <option value="Japan">Japan</option>
          <option value="China">China</option>
          <option value="India">India</option>
          <option value="Brazil">Brazil</option>
        </select>
      </div>

      <button type="submit" class="submit-button">Submit</button>
    </form>
  </div>

  <div class="popup-overlay" id="floating-popup-overlay">
    <div class="popup" id="floating-popup">
      <span class="close-x" onclick="closePopup('floating-popup-overlay')">&times;</span>
      <h2>Limited Time Offer</h2>
      <p>Get 20% off your first purchase! Don't miss out!</p>
      <button class="popup-close" onclick="closePopup('floating-popup-overlay')">No Thanks</button>
    </div>
  </div>

  <div class="popup-overlay" id="popup-newsletter">
    <div class="popup" style="top: 20%; left: 50%; transform: translateX(-50%);">
      <span class="close-x" onclick="closePopup('popup-newsletter')">&times;</span>
      <h2>Special Offer!</h2>
      <p>Subscribe to our newsletter for exclusive deals and updates.</p>
      <button class="popup-close" onclick="closePopup('popup-newsletter')">Close</button>
    </div>
  </div>

  <div id="cookie-bar">
    <span>This website uses cookies to improve your experience. By continuing, you accept our cookie policy.</span>
    <button onclick="closeCookieBar()">Accept</button>
  </div>

  <script>
    function closePopup(id) {
      document.getElementById(id).style.display = 'none';
    }

    function closeCookieBar() {
      document.getElementById('cookie-bar').style.display = 'none';
    }

    // 显示cookie和浮动弹窗
    document.getElementById('cookie-bar').style.display = 'flex';
    const floatingPopup = document.getElementById('floating-popup-overlay');
    floatingPopup.style.display = 'flex';

    // 浮动弹窗移动逻辑
    function startFloating(popup) {
      const w = window.innerWidth;
      const h = window.innerHeight;
      let x = w/2 - popup.offsetWidth/2;
      let y = h/2 - popup.offsetHeight/2;
      let dx = (Math.random() - 0.5) * 1.5; // 控制速度
      let dy = (Math.random() - 0.5) * 1.5;

      function move() {
        x += dx;
        y += dy;
        if (x < 0 || x + popup.offsetWidth > w) dx = -dx;
        if (y < 0 || y + popup.offsetHeight > h) dy = -dy;
        popup.style.left = x + 'px';
        popup.style.top = y + 'px';
        requestAnimationFrame(move);
      }
      move();
    }
    startFloating(document.getElementById('floating-popup'));

    // 点击第一个输入框后显示其他弹窗
    let firstInput = document.getElementById('name');
    let otherPopupsShown = false;
    firstInput.addEventListener('focus', () => {
      if (!otherPopupsShown) {
        document.getElementById('popup-newsletter').style.display = 'flex';
        otherPopupsShown = true;
      }
    });

    // Simple SHA-256 implementation (truncated to first 8 characters)
    async function sha256(message) {
      const msgBuffer = new TextEncoder().encode(message);
      const hashBuffer = await crypto.subtle.digest('SHA-256', msgBuffer);
      const hashArray = Array.from(new Uint8Array(hashBuffer));
      const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
      return hashHex.substring(0, 8);  // Use only first 8 characters
    }

    document.getElementById('main-form').addEventListener('submit', async function(e) {
      e.preventDefault();
      const name = document.getElementById('name').value;
      const email = document.getElementById('email').value;
      const country = document.getElementById('country').value;

      if(name && email && country){
        // No normalization needed for these fields
        const dataString = name + '|' + email + '|' + country;
        const hash = await sha256(dataString);
        
        document.body.innerHTML = `
          <div style="padding: 20px; max-width: 600px; margin: 0 auto;">
            <h1>Success!</h1>
            <div style="background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
              <h2>Form Submitted Successfully!</h2>
              <p style="font-family: monospace; word-break: break-all;">Verification: ${hash}</p>
            </div>
          </div>
        `;
      }
    });
  </script>
</body>
</html>"""

  def is_successful(self, env: interface.AsyncEnv) -> float:
    """Check if the form was successfully submitted with correct information."""
    # First check parent class validation (Chrome app + "Success!" text)
    if super().is_successful(env) == 0.0:
      return 0.0
    
    # Calculate expected hash from submitted data (use first 8 characters)
    # No normalization needed - these fields don't have formatting characters
    data_string = (
        self.params["name"] + '|' +
        self.params["email"] + '|' +
        self.params["country"]
    )
    expected_hash = hashlib.sha256(data_string.encode()).hexdigest()[:8]
    
    # Check if hash is displayed in UI
    ui_elements = representation_utils.forest_to_ui_elements(
        env.get_state().forest,
        exclude_invisible_elements=False,
    )
    
    for element in ui_elements:
      if element.text and expected_hash in element.text:
        return 1.0
    
    return 0.0


class BrowserAdBlock(BrowserTask):
  """Task for closing ad overlays blocking content."""

  complexity = 2.5
  @property
  def goal(self) -> str:
    return (
        self.preamble
        + ' Then read the secret code, and enter it in the form.'
    )

  HTML = """<!DOCTYPE html>
<html>
<head>
  <title>Article Page</title>
  <style>
    body {
      font-family: Arial, sans-serif;
      margin: 0;
      padding: 20px;
      background-color: #f5f5f5;
    }

    .article-container {
      max-width: 700px;
      margin: 0 auto;
      padding: 30px;
      background-color: white;
      border-radius: 10px;
      box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    }

    h1 {
      font-size: 32px;
      margin-bottom: 20px;
      color: #333;
    }

    .article-content {
      font-size: 18px;
      line-height: 1.6;
      color: #555;
      margin-bottom: 30px;
    }

    .secret-code-box {
      padding: 20px;
      background-color: #fff3cd;
      border: 2px solid #ffc107;
      border-radius: 8px;
      text-align: center;
      margin: 30px 0;
    }

    .secret-code {
      font-size: 36px;
      font-weight: bold;
      color: #856404;
      letter-spacing: 3px;
      margin: 10px 0;
    }

    .form-group {
      margin: 20px 0;
    }

    label {
      display: block;
      font-size: 18px;
      font-weight: bold;
      margin-bottom: 10px;
      color: #333;
    }

    input[type="text"] {
      width: 100%;
      padding: 12px;
      font-size: 18px;
      border: 2px solid #ddd;
      border-radius: 5px;
      box-sizing: border-box;
    }

    .submit-button {
      width: 100%;
      padding: 15px;
      font-size: 20px;
      font-weight: bold;
      background-color: #4CAF50;
      color: white;
      border: none;
      border-radius: 5px;
      cursor: pointer;
      margin-top: 15px;
    }

    .submit-button:hover {
      background-color: #45a049;
    }

    /* Ad overlay styles */
    .ad-overlay {
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      background-color: rgba(0, 0, 0, 0.85);
      z-index: 9999;
      display: flex;
      justify-content: center;
      align-items: center;
    }

    .ad-content {
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      padding: 40px;
      border-radius: 15px;
      max-width: 500px;
      text-align: center;
      color: white;
      position: relative;
      box-shadow: 0 10px 40px rgba(0,0,0,0.3);
    }

    .ad-close {
      position: absolute;
      top: 10px;
      right: 15px;
      font-size: 32px;
      font-weight: bold;
      color: white;
      cursor: pointer;
      line-height: 1;
      padding: 5px 10px;
      border-radius: 5px;
      background-color: rgba(255,255,255,0.2);
    }

    .ad-close:hover {
      background-color: rgba(255,255,255,0.3);
    }

    .ad-content h2 {
      font-size: 32px;
      margin-bottom: 15px;
    }

    .ad-content p {
      font-size: 18px;
      margin-bottom: 20px;
      line-height: 1.5;
    }

    .ad-button {
      padding: 15px 40px;
      font-size: 20px;
      font-weight: bold;
      background-color: white;
      color: #667eea;
      border: none;
      border-radius: 8px;
      cursor: pointer;
      margin: 10px;
    }

    .ad-button:hover {
      background-color: #f0f0f0;
    }

    .small-text {
      font-size: 12px;
      margin-top: 20px;
      opacity: 0.8;
    }
  </style>
</head>
<body>
  <div class="article-container">
    <h1>Welcome to Our Article</h1>
    
    <div class="article-content">
      <p>Thank you for visiting our website. To access the exclusive content, 
      you need to enter the secret code displayed below.</p>
      
      <p>This code is required to verify that you can view the content properly.</p>
    </div>

    <div class="secret-code-box">
      <p style="margin: 0; font-size: 16px;">Your Secret Code:</p>
      <div class="secret-code" id="secret-code"></div>
    </div>

    <form id="code-form">
      <div class="form-group">
        <label for="code-input">Enter the Secret Code:</label>
        <input type="text" id="code-input" name="code" required 
               placeholder="Enter the code here">
      </div>
      <button type="submit" class="submit-button">Submit Code</button>
    </form>
  </div>

  <!-- Ad Overlay -->
  <div class="ad-overlay" id="ad-overlay">
    <div class="ad-content">
      <span class="ad-close" id="close-ad">&times;</span>
      <h2>Special Offer!</h2>
      <p>Get 50% OFF on our premium subscription!</p>
      <p>Limited time offer - Don't miss out!</p>
      <button class="ad-button" id="learn-more">Learn More</button>
      <button class="ad-button" id="no-thanks">No Thanks</button>
      <p class="small-text">Terms and conditions apply</p>
    </div>
  </div>

  <script>
    class SeededRNG {
      constructor(seed) {
        this.seed = seed;
      }

      random() {
        const a = 1664525;
        const c = 1013904223;
        const m = 2 ** 32;
        this.seed = (a * this.seed + c) % m;
        return this.seed / m;
      }
    }

    const rng = new SeededRNG(new Date().getTime());

    // Generate random secret code (4 characters: letters and numbers)
    const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
    let secretCode = '';
    for (let i = 0; i < 4; i++) {
      secretCode += chars.charAt(Math.floor(rng.random() * chars.length));
    }

    document.getElementById('secret-code').textContent = secretCode;

    function closeAd() {
      document.getElementById('ad-overlay').style.display = 'none';
    }

    // Ensure DOM is ready before binding
    document.addEventListener('DOMContentLoaded', () => {
      const closeBtn = document.getElementById('close-ad');
      const noThanksBtn = document.getElementById('no-thanks');
      const adOverlay = document.getElementById('ad-overlay');
      const learnMoreBtn = document.getElementById('learn-more');

      if (closeBtn) {
        closeBtn.addEventListener('click', closeAd);
      }

      if (noThanksBtn) {
        noThanksBtn.addEventListener('click', function(e) {
          e.preventDefault();
          try {
            if (rng.random() < 0.5) {
              const url = 'https://github.com/Silung/android_world_plus';
              const w = window.open(url, '_blank');
              if (!w) {
                window.location.href = url;
                return;
              }
            }
          } finally {
            closeAd();
          }
        });
      }

      if (learnMoreBtn) {
        learnMoreBtn.addEventListener('click', function(e) {
          e.preventDefault();
          window.location.href = 'https://github.com/Silung/android_world_plus';
        });
      }

      // Optional: Also allow clicking outside ad to close (improve UX)
      if (adOverlay) {
        adOverlay.addEventListener('click', function(e) {
          if (e.target === adOverlay) {
            closeAd();
          }
        });
      }
    });

    // Handle form submission
    document.getElementById('code-form').addEventListener('submit', function(e) {
      e.preventDefault();
      const enteredCode = document.getElementById('code-input').value.toUpperCase();
      if (enteredCode === secretCode) {
        document.body.innerHTML = '<div style="text-align:center; padding:50px; font-size:24px;">Success! Access Granted.</div>';
      } else {
        alert('Incorrect code. Please try again.');
      }
    });
  </script>
</body>
</html>"""


class BrowserMultiStepForm(BrowserTask):
  """Task for completing a multi-step registration form."""

  complexity = 4.0
  schema = {
      "type": "object",
      "properties": {
          "first_name": {"type": "string"},
          "last_name": {"type": "string"},
          "dob": {"type": "string"},
          "email": {"type": "string"},
          "phone": {"type": "string"},
          "city": {"type": "string"},
          "username": {"type": "string"},
          "language": {"type": "string"},
          "newsletter": {"type": "string"},
      },
      "required": ["first_name", "last_name", "dob", "email", "phone", "city", "username", "language", "newsletter"],
  }
  template = (
      " Then complete the 3-step registration form with the following information:\n"
      "First Name: {first_name}, Last Name: {last_name}, Date of Birth: {dob}, "
      "Email: {email}, Phone: {phone}, City: {city}, "
      "Username: {username}, Language: {language}, Newsletter: {newsletter}"
  )

  @classmethod
  def generate_random_params(cls) -> dict[str, str]:
    first_names = [
        "John", "Emma", "Michael", "Sophia", "William",
        "Olivia", "James", "Ava", "Robert", "Isabella"
    ]
    last_names = [
        "Smith", "Johnson", "Williams", "Brown", "Jones",
        "Garcia", "Miller", "Davis", "Rodriguez", "Martinez"
    ]
    cities = [
        "New York", "Los Angeles", "Chicago", "Houston", "Phoenix",
        "Philadelphia", "San Antonio", "San Diego", "Dallas", "San Jose"
    ]
    usernames = [
        "user123", "techguru", "coolcat99", "happyuser", "starlight",
        "oceanwave", "mountainking", "skywalker", "phoenix2024", "dragonfly"
    ]
    languages = ["en", "es", "fr", "de", "zh"]
    language_names = {
        "en": "English",
        "es": "Spanish", 
        "fr": "French",
        "de": "German",
        "zh": "Chinese"
    }
    newsletters = ["weekly", "monthly", "never"]
    newsletter_names = {
        "weekly": "Weekly",
        "monthly": "Monthly",
        "never": "Never"
    }
    
    first_name = random.choice(first_names)
    last_name = random.choice(last_names)
    # Generate date in MM/DD/YYYY format
    month = random.randint(1, 12)
    day = random.randint(1, 28)  # Safe for all months
    year = random.randint(1970, 2005)
    dob = f"{month:02d}/{day:02d}/{year}"
    
    email = f"{first_name.lower()}.{last_name.lower()}@example.com"
    # Generate phone in (XXX) XXX-XXXX format
    phone = f"({random.randint(200, 999)}) {random.randint(200, 999)}-{random.randint(1000, 9999)}"
    city = random.choice(cities)
    username = random.choice(usernames)
    language = random.choice(languages)
    newsletter = random.choice(newsletters)
    
    params = {
        "first_name": first_name,
        "last_name": last_name,
        "dob": dob,
        "email": email,
        "phone": phone,
        "city": city,
        "username": username,
        "language": language,
        "language_display": language_names[language],
        "newsletter": newsletter,
        "newsletter_display": newsletter_names[newsletter],
        'browser_task_seed': random.randint(0, 2**32 - 1)
    }
    return params

  @property
  def goal(self) -> str:
    return self.preamble + self.template.format(**self.params)

  HTML = """\
<!DOCTYPE html>
<html>
<head>
  <title>Multi-Step Registration</title>
  <style>
    body {
      font-family: Arial, sans-serif;
      margin: 0;
      padding: 20px;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      min-height: 100vh;
    }

    .form-container {
      max-width: 600px;
      margin: 30px auto;
      padding: 40px;
      background-color: white;
      border-radius: 15px;
      box-shadow: 0 10px 40px rgba(0,0,0,0.3);
    }

    h1 {
      text-align: center;
      font-size: 32px;
      margin-bottom: 10px;
      color: #333;
    }

    .progress-bar {
      display: flex;
      justify-content: space-between;
      margin: 30px 0;
      position: relative;
    }

    .progress-step {
      flex: 1;
      text-align: center;
      position: relative;
    }

    .progress-circle {
      width: 40px;
      height: 40px;
      border-radius: 50%;
      background-color: #ddd;
      color: #999;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      font-weight: bold;
      font-size: 18px;
      margin-bottom: 5px;
      position: relative;
      z-index: 2;
    }

    .progress-circle.active {
      background-color: #4CAF50;
      color: white;
    }

    .progress-circle.completed {
      background-color: #2196F3;
      color: white;
    }

    .progress-label {
      font-size: 14px;
      color: #666;
    }

    .progress-line {
      position: absolute;
      top: 20px;
      left: 0;
      right: 0;
      height: 3px;
      background-color: #ddd;
      z-index: 1;
    }

    .progress-line-fill {
      height: 100%;
      background-color: #2196F3;
      transition: width 0.3s ease;
    }

    .form-step {
      display: none;
    }

    .form-step.active {
      display: block;
    }

    .form-group {
      margin-bottom: 20px;
    }

    label {
      display: block;
      margin-bottom: 8px;
      font-size: 16px;
      font-weight: bold;
      color: #333;
    }

    input[type="text"],
    input[type="email"],
    input[type="tel"],
    select {
      width: 100%;
      padding: 12px;
      font-size: 16px;
      border: 2px solid #ddd;
      border-radius: 5px;
      box-sizing: border-box;
    }

    input:focus, select:focus {
      border-color: #667eea;
      outline: none;
    }

    .required {
      color: red;
    }

    .button-group {
      display: flex;
      justify-content: space-between;
      margin-top: 30px;
    }

    .btn {
      padding: 12px 30px;
      font-size: 18px;
      font-weight: bold;
      border: none;
      border-radius: 5px;
      cursor: pointer;
      transition: background-color 0.3s;
    }

    .btn-next, .btn-submit {
      background-color: #4CAF50;
      color: white;
    }

    .btn-next:hover, .btn-submit:hover {
      background-color: #45a049;
    }

    .btn-prev {
      background-color: #999;
      color: white;
    }

    .btn-prev:hover {
      background-color: #777;
    }

    .error-message {
      color: red;
      font-size: 14px;
      margin-top: 5px;
      display: none;
    }
  </style>
</head>
<body>
  <div class="form-container">
    <h1>Create Account</h1>
    
    <div class="progress-bar">
      <div class="progress-line">
        <div class="progress-line-fill" id="progress-fill"></div>
      </div>
      <div class="progress-step">
        <div class="progress-circle active" id="circle-1">1</div>
        <div class="progress-label">Personal Info</div>
      </div>
      <div class="progress-step">
        <div class="progress-circle" id="circle-2">2</div>
        <div class="progress-label">Contact</div>
      </div>
      <div class="progress-step">
        <div class="progress-circle" id="circle-3">3</div>
        <div class="progress-label">Preferences</div>
      </div>
    </div>

    <form id="registration-form">
      <!-- Step 1: Personal Information -->
      <div class="form-step active" id="step-1">
        <h2>Step 1: Personal Information</h2>
        <div class="form-group">
          <label>First Name <span class="required">*</span></label>
          <input type="text" id="first-name" required>
        </div>
        <div class="form-group">
          <label>Last Name <span class="required">*</span></label>
          <input type="text" id="last-name" required>
        </div>
        <div class="form-group">
          <label>Date of Birth <span class="required">*</span></label>
          <input type="text" id="dob" placeholder="MM/DD/YYYY" required>
        </div>
        <div class="button-group">
          <div></div>
          <button type="button" class="btn btn-next" onclick="nextStep(1)">Next</button>
        </div>
      </div>

      <!-- Step 2: Contact Information -->
      <div class="form-step" id="step-2">
        <h2>Step 2: Contact Information</h2>
        <div class="form-group">
          <label>Email Address <span class="required">*</span></label>
          <input type="email" id="email" required>
        </div>
        <div class="form-group">
          <label>Phone Number <span class="required">*</span></label>
          <input type="tel" id="phone" placeholder="(123) 456-7890" required>
        </div>
        <div class="form-group">
          <label>City <span class="required">*</span></label>
          <input type="text" id="city" required>
        </div>
        <div class="button-group">
          <button type="button" class="btn btn-prev" onclick="prevStep(2)">Previous</button>
          <button type="button" class="btn btn-next" onclick="nextStep(2)">Next</button>
        </div>
      </div>

      <!-- Step 3: Preferences -->
      <div class="form-step" id="step-3">
        <h2>Step 3: Preferences</h2>
        <div class="form-group">
          <label>Username <span class="required">*</span></label>
          <input type="text" id="username" required>
        </div>
        <div class="form-group">
          <label>Preferred Language <span class="required">*</span></label>
          <select id="language" required>
            <option value="">Select a language</option>
            <option value="en">English</option>
            <option value="es">Spanish</option>
            <option value="fr">French</option>
            <option value="de">German</option>
            <option value="zh">Chinese</option>
          </select>
        </div>
        <div class="form-group">
          <label>Newsletter Preference <span class="required">*</span></label>
          <select id="newsletter" required>
            <option value="">Select preference</option>
            <option value="weekly">Weekly</option>
            <option value="monthly">Monthly</option>
            <option value="never">Never</option>
          </select>
        </div>
        <div class="button-group">
          <button type="button" class="btn btn-prev" onclick="prevStep(3)">Previous</button>
          <button type="submit" class="btn btn-submit">Submit</button>
        </div>
      </div>
    </form>
  </div>

  <script>
    let currentStep = 1;

    function updateProgress() {
      // Update progress bar
      const progressFill = document.getElementById('progress-fill');
      progressFill.style.width = ((currentStep - 1) / 2) * 100 + '%';

      // Update circles
      for (let i = 1; i <= 3; i++) {
        const circle = document.getElementById(`circle-${i}`);
        circle.classList.remove('active', 'completed');
        if (i < currentStep) {
          circle.classList.add('completed');
        } else if (i === currentStep) {
          circle.classList.add('active');
        }
      }
    }

    function validateStep(step) {
      let isValid = true;
      const inputs = document.querySelectorAll(`#step-${step} input[required], #step-${step} select[required]`);
      
      inputs.forEach(input => {
        if (!input.value.trim()) {
          isValid = false;
          input.style.borderColor = 'red';
        } else {
          input.style.borderColor = '#ddd';
        }
      });

      return isValid;
    }

    function nextStep(step) {
      if (validateStep(step)) {
        document.getElementById(`step-${step}`).classList.remove('active');
        currentStep++;
        document.getElementById(`step-${currentStep}`).classList.add('active');
        updateProgress();
        window.scrollTo(0, 0);
      } else {
        alert('Please fill in all required fields.');
      }
    }

    function prevStep(step) {
      document.getElementById(`step-${step}`).classList.remove('active');
      currentStep--;
      document.getElementById(`step-${currentStep}`).classList.add('active');
      updateProgress();
      window.scrollTo(0, 0);
    }

    // Normalize string by removing special characters (keep only alphanumeric)
    // Only use this for formatting characters like phone numbers and dates
    function normalizeString(str) {
      return str.replace(/[^a-zA-Z0-9]/g, '');
    }

    document.getElementById('registration-form').addEventListener('submit', function(e) {
      e.preventDefault();
      
      if (validateStep(3)) {
        // Collect all form data
        const firstName = document.getElementById('first-name').value;
        const lastName = document.getElementById('last-name').value;
        const dob = document.getElementById('dob').value;
        const email = document.getElementById('email').value;
        const phone = document.getElementById('phone').value;
        const city = document.getElementById('city').value;
        const username = document.getElementById('username').value;
        const language = document.getElementById('language').value;
        const newsletter = document.getElementById('newsletter').value;
        
        // Only normalize phone and date fields - other fields keep special characters
        const dataString = firstName + '|' + lastName + '|' + normalizeString(dob) + '|' + 
                          email + '|' + normalizeString(phone) + '|' + city + '|' + 
                          username + '|' + language + '|' + newsletter;
        
        crypto.subtle.digest('SHA-256', new TextEncoder().encode(dataString)).then(hashBuffer => {
          const hashArray = Array.from(new Uint8Array(hashBuffer));
          const hash = hashArray.map(b => b.toString(16).padStart(2, '0')).join('').substring(0, 8);
          
          document.body.innerHTML = `
            <div style="padding: 20px; max-width: 600px; margin: 50px auto;">
              <h1>Success!</h1>
              <div style="background: white; padding: 30px; border-radius: 10px; box-shadow: 0 10px 40px rgba(0,0,0,0.3);">
                <h2>Registration Complete!</h2>
                <p style="font-family: monospace; word-break: break-all; font-size: 14px;">Verification: ${hash}</p>
              </div>
            </div>
          `;
        });
      } else {
        alert('Please fill in all required fields.');
      }
    });

    // Make functions globally accessible
    window.nextStep = nextStep;
    window.prevStep = prevStep;
  </script>
</body>
</html>"""

  def is_successful(self, env: interface.AsyncEnv) -> float:
    """Check if the multi-step form was successfully completed with correct information."""
    # First check parent class validation (Chrome app + "Success!" text)
    if super().is_successful(env) == 0.0:
      return 0.0
    
    # Normalize strings by removing special characters (keep only alphanumeric)
    # Only use this for formatting characters like phone numbers and dates
    def normalize_string(s):
      return re.sub(r'[^a-zA-Z0-9]', '', s)
    
    # Calculate expected hash from submitted data (use first 8 characters)
    # Only normalize phone and date fields - other fields keep special characters
    data_string = (
        self.params["first_name"] + '|' +
        self.params["last_name"] + '|' +
        normalize_string(self.params["dob"]) + '|' +
        self.params["email"] + '|' +
        normalize_string(self.params["phone"]) + '|' +
        self.params["city"] + '|' +
        self.params["username"] + '|' +
        self.params["language"] + '|' +
        self.params["newsletter"]
    )
    expected_hash = hashlib.sha256(data_string.encode()).hexdigest()[:8]
    
    # Check if hash is displayed in UI
    ui_elements = representation_utils.forest_to_ui_elements(
        env.get_state().forest,
        exclude_invisible_elements=False,
    )
    
    for element in ui_elements:
      if element.text and expected_hash in element.text:
        return 1.0
    
    return 0.0


class BrowserFileUpload(BrowserTask):
  """Task for simulating file selection and upload."""

  complexity = 3.0
  schema = {
      "type": "object",
      "properties": {
          "required_file": {"type": "string"},
          "noise_candidates": {"type": "array"},
      },
      "required": ["required_file", "noise_candidates"],
  }
  template = (
      " Then click the file upload button, select the file named {required_file} "
      "from the Downloads folder, and upload it."
  )

  @classmethod
  def generate_random_params(cls) -> dict[str, str]:
    # Use the same file generation mechanism as FilesDeleteFile
    noise_candidates = user_data_generation.EMULATOR_DIRECTORIES["Download"]
    _, ext_part = os.path.splitext(noise_candidates[0])
    required_file = user_data_generation.generate_random_file_name() + ext_part
    
    params = {
        "required_file": required_file,
        "noise_candidates": noise_candidates,
        'browser_task_seed': random.randint(0, 2**32 - 1)
    }
    return params

  @property
  def goal(self) -> str:
    return self.preamble + self.template.format(**self.params)

  def initialize_task(self, env: interface.AsyncEnv):
    super().initialize_task(env)
    # Create the required file and noise files in Downloads directory
    # This follows the same pattern as FilesDeleteFile
    from android_world.utils import file_utils
    download_path = device_constants.DOWNLOAD_DATA
    
    # Create the required file first
    file_utils.create_file(
        self.params["required_file"],
        download_path,
        env.controller
    )
    
    # Generate noise files (distractors)
    user_data_generation.generate_noise_files(
        self.params["required_file"],
        download_path,
        env.controller,
        self.params["noise_candidates"],
    )
    
    # Verify file was created
    if not file_utils.check_file_or_folder_exists(
        self.params["required_file"], download_path, env.controller
    ):
      raise RuntimeError(f"File {self.params['required_file']} was not created in Downloads.")

  HTML = """\
<!DOCTYPE html>
<html>
<head>
  <title>File Upload</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    body {
      font-family: Arial, sans-serif;
      margin: 0;
      padding: 20px;
      background-color: #f5f5f5;
    }

    .upload-container {
      max-width: 600px;
      margin: 50px auto;
      padding: 40px;
      background-color: white;
      border-radius: 10px;
      box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    }

    h1 {
      text-align: center;
      font-size: 32px;
      margin-bottom: 10px;
      color: #333;
    }

    .instruction {
      text-align: center;
      font-size: 16px;
      color: #666;
      margin-bottom: 30px;
    }

    .file-input-area {
      border: 3px dashed #ddd;
      border-radius: 8px;
      padding: 40px 20px;
      text-align: center;
      margin-bottom: 30px;
      background-color: #fafafa;
      cursor: pointer;
      transition: all 0.3s;
    }

    .file-input-area:hover {
      border-color: #2196F3;
      background-color: #f0f8ff;
    }

    .file-input-area.has-file {
      border-color: #4CAF50;
      background-color: #e8f5e9;
    }

    .file-icon {
      font-size: 48px;
      margin-bottom: 15px;
    }

    .file-label {
      font-size: 18px;
      font-weight: bold;
      color: #666;
      margin-bottom: 10px;
    }

    .file-hint {
      font-size: 14px;
      color: #999;
      margin-top: 10px;
    }

    #file-input {
      display: none;
    }

    .selected-file {
      padding: 15px;
      background-color: #e3f2fd;
      border: 2px solid #2196F3;
      border-radius: 5px;
      margin-bottom: 20px;
      display: none;
    }

    .selected-file.show {
      display: block;
    }

    .selected-file-label {
      font-size: 14px;
      color: #666;
      margin-bottom: 5px;
    }

    .selected-file-name {
      font-size: 18px;
      font-weight: bold;
      color: #2196F3;
      word-break: break-all;
    }

    .upload-button {
      width: 100%;
      padding: 15px;
      font-size: 20px;
      font-weight: bold;
      background-color: #4CAF50;
      color: white;
      border: none;
      border-radius: 5px;
      cursor: pointer;
      transition: background-color 0.3s;
    }

    .upload-button:hover:not(:disabled) {
      background-color: #45a049;
    }

    .upload-button:disabled {
      background-color: #ccc;
      cursor: not-allowed;
    }
  </style>
</head>
<body>
  <div class="upload-container">
    <h1>File Upload</h1>
    <p class="instruction">Please select a file from Downloads folder and upload it</p>

    <div class="file-input-area" id="file-area" onclick="document.getElementById('file-input').click()">
      <div class="file-icon">[FILE]</div>
      <div class="file-label">Click to select file</div>
      <div class="file-hint">Select from Downloads folder</div>
    </div>

    <input type="file" id="file-input" accept="*/*">

    <div class="selected-file" id="selected-file">
      <div class="selected-file-label">Selected File:</div>
      <div class="selected-file-name" id="file-name"></div>
    </div>

    <button class="upload-button" id="upload-btn" disabled onclick="uploadFile()">
      Upload File
    </button>
  </div>

  <script>
    let selectedFileName = null;

    // Handle file selection
    document.getElementById('file-input').addEventListener('change', function(e) {
      const file = e.target.files[0];
      if (file) {
        selectedFileName = file.name;
        
        // Update UI
        document.getElementById('file-area').classList.add('has-file');
        document.getElementById('file-area').querySelector('.file-label').textContent = 'File selected';
        
        document.getElementById('selected-file').classList.add('show');
        document.getElementById('file-name').textContent = selectedFileName;
        
        document.getElementById('upload-btn').disabled = false;
      }
    });

    function uploadFile() {
      if (selectedFileName) {
        // No normalization - file name characters are meaningful (use first 8 characters)
        crypto.subtle.digest('SHA-256', new TextEncoder().encode(selectedFileName)).then(hashBuffer => {
          const hashArray = Array.from(new Uint8Array(hashBuffer));
          const hash = hashArray.map(b => b.toString(16).padStart(2, '0')).join('').substring(0, 8);
          
          document.body.innerHTML = `
            <div style="padding: 20px; max-width: 600px; margin: 50px auto;">
              <h1>Success!</h1>
              <div style="background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                <h2>File Uploaded Successfully!</h2>
                <p style="font-family: monospace; word-break: break-all; font-size: 14px;">Verification: ${hash}</p>
              </div>
            </div>
          `;
        });
      }
    }

    // Make uploadFile globally accessible
    window.uploadFile = uploadFile;
  </script>
</body>
</html>"""

  def is_successful(self, env: interface.AsyncEnv) -> float:
    """Check if the correct file was uploaded."""
    # First check parent class validation (Chrome app + "Success!" text)
    if super().is_successful(env) == 0.0:
      return 0.0
    
    # Calculate expected hash from the required file name (use first 8 characters)
    # No normalization - file name characters are meaningful
    expected_hash = hashlib.sha256(
        self.params["required_file"].encode()
    ).hexdigest()[:8]
    
    # Check if hash is displayed in UI
    ui_elements = representation_utils.forest_to_ui_elements(
        env.get_state().forest,
        exclude_invisible_elements=False,
    )
    
    for element in ui_elements:
      if element.text and expected_hash in element.text:
        return 1.0
    
    return 0.0


class BrowserRetry(BrowserTask):
  """Task for handling submission failure and retry logic."""

  complexity = 3.5
  schema = {
      "type": "object",
      "properties": {
          "name": {"type": "string"},
          "email": {"type": "string"},
          "ranking": {"type": "string"},
          "comments": {"type": "string"},
      },
      "required": ["name", "email", "ranking", "comments"],
  }
  template = (
      " Then fill in the survey form with following information and submit:\n"
      'Name: {name}, Email: {email}, Ranking: {ranking}, Comments: "{comments}"'
  )

  @classmethod
  def generate_random_params(cls) -> dict[str, str]:
    name_email_pairs = [
        ("Bob Smith", "bob.smith@co.uk"),
        ("Alice Johnson", "alice.j@test.com"),
        ("Charlie Davis", "charlie.d@example.com"),
        ("Diana Garcia", "diana.g@mail.com"),
        ("Edward Wilson", "edward.w@demo.com"),
        ("Fiona Martinez", "fiona.m@site.com"),
        ("George Brown", "george.b@test.net"),
        ("Hannah Lee", "hannah.l@example.org"),
        ("Isaac Taylor", "isaac.t@web.com"),
        ("Julia Anderson", "julia.a@service.com"),
    ]
    
    comments_list = [
        "Absolutely delicious food, exceptional service, and a cozy atmosphere",
        "Great experience overall, highly recommend to everyone",
        "The quality exceeded my expectations, will visit again",
        "Professional staff and amazing attention to detail",
        "Outstanding service from start to finish",
        "Very impressed with the quality and presentation",
        "Fantastic experience, worth every penny",
        "Exceeded all expectations, truly remarkable",
        "Impeccable service and wonderful ambiance",
        "Best experience I've had in a long time",
    ]
    
    rankings = ["1", "2", "3", "4", "5"]
    
    name, email = random.choice(name_email_pairs)
    ranking = random.choice(rankings)
    comments = random.choice(comments_list)
    
    params = {
        "name": name,
        "email": email,
        "ranking": ranking,
        "comments": comments,
        'browser_task_seed': random.randint(0, 2**32 - 1)
    }
    return params

  @property
  def goal(self) -> str:
    return self.preamble + self.template.format(**self.params)

  HTML = """<!DOCTYPE html>
<html>
<head>
  <title>Survey Form</title>
  <style>
    body {
      font-family: Arial, sans-serif;
      margin: 0;
      padding: 20px;
      background-color: #f5f5f5;
    }

    .survey-container {
      max-width: 600px;
      margin: 50px auto;
      padding: 40px;
      background-color: white;
      border-radius: 10px;
      box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    }

    h1 {
      text-align: center;
      font-size: 32px;
      margin-bottom: 10px;
      color: #333;
    }

    .subtitle {
      text-align: center;
      font-size: 16px;
      color: #666;
      margin-bottom: 30px;
    }

    .form-group {
      margin-bottom: 25px;
    }

    label {
      display: block;
      margin-bottom: 8px;
      font-size: 16px;
      font-weight: bold;
      color: #333;
    }

    input[type="text"],
    input[type="email"],
    textarea,
    select {
      width: 100%;
      padding: 12px;
      font-size: 16px;
      border: 2px solid #ddd;
      border-radius: 5px;
      box-sizing: border-box;
      font-family: Arial, sans-serif;
    }

    textarea {
      resize: vertical;
      min-height: 100px;
    }

    input:focus, textarea:focus, select:focus {
      border-color: #2196F3;
      outline: none;
    }

    .required {
      color: red;
    }

    .rating-group {
      display: flex;
      gap: 10px;
      margin-top: 8px;
    }

    .rating-btn {
      flex: 1;
      padding: 10px;
      font-size: 16px;
      font-weight: bold;
      background-color: #f0f0f0;
      border: 2px solid #ddd;
      border-radius: 5px;
      cursor: pointer;
      transition: all 0.3s;
    }

    .rating-btn:hover {
      border-color: #2196F3;
      background-color: #e3f2fd;
    }

    .rating-btn.selected {
      background-color: #4CAF50;
      border-color: #4CAF50;
      color: white;
    }

    .submit-button {
      width: 100%;
      padding: 15px;
      font-size: 20px;
      font-weight: bold;
      background-color: #2196F3;
      color: white;
      border: none;
      border-radius: 5px;
      cursor: pointer;
      margin-top: 20px;
      transition: background-color 0.3s;
    }

    .submit-button:hover:not(:disabled) {
      background-color: #0b7dda;
    }

    .submit-button:disabled {
      background-color: #ccc;
      cursor: not-allowed;
    }

    .error-message {
      background-color: #ffebee;
      border: 2px solid #f44336;
      border-radius: 8px;
      padding: 20px;
      margin: 20px 0;
      display: none;
    }

    .error-message.show {
      display: block;
    }

    .error-title {
      font-size: 20px;
      font-weight: bold;
      color: #c62828;
      margin-bottom: 10px;
      display: flex;
      align-items: center;
      gap: 10px;
    }

    .error-text {
      font-size: 16px;
      color: #d32f2f;
      margin-bottom: 15px;
    }

    .retry-button {
      padding: 12px 30px;
      font-size: 18px;
      font-weight: bold;
      background-color: #ff9800;
      color: white;
      border: none;
      border-radius: 5px;
      cursor: pointer;
      transition: background-color 0.3s;
    }

    .retry-button:hover {
      background-color: #f57c00;
    }

    .loading {
      text-align: center;
      padding: 20px;
      font-size: 18px;
      color: #666;
    }

    .spinner {
      border: 4px solid #f3f3f3;
      border-top: 4px solid #2196F3;
      border-radius: 50%;
      width: 40px;
      height: 40px;
      animation: spin 1s linear infinite;
      margin: 20px auto;
    }

    @keyframes spin {
      0% { transform: rotate(0deg); }
      100% { transform: rotate(360deg); }
    }
  </style>
</head>
<body>
  <div class="survey-container">
    <h1>Survey</h1>
    <p class="subtitle">Help us improve our service</p>

    <form id="survey-form">
      <div class="form-group">
        <label>Name <span class="required">*</span></label>
        <input type="text" id="name" required>
      </div>

      <div class="form-group">
        <label>Email <span class="required">*</span></label>
        <input type="email" id="email" required>
      </div>

      <div class="form-group">
        <label>How satisfied are you with our service? <span class="required">*</span></label>
        <div class="rating-group">
          <button type="button" class="rating-btn" data-rating="1" onclick="selectRating(1)">1</button>
          <button type="button" class="rating-btn" data-rating="2" onclick="selectRating(2)">2</button>
          <button type="button" class="rating-btn" data-rating="3" onclick="selectRating(3)">3</button>
          <button type="button" class="rating-btn" data-rating="4" onclick="selectRating(4)">4</button>
          <button type="button" class="rating-btn" data-rating="5" onclick="selectRating(5)">5</button>
        </div>
        <input type="hidden" id="rating" required>
      </div>

      <div class="form-group">
        <label>Additional Comments</label>
        <textarea id="comments" placeholder="Tell us more about your experience..."></textarea>
      </div>

      <button type="submit" class="submit-button" id="submit-btn">Submit Survey</button>
    </form>

    <div class="error-message" id="error-message">
      <div class="error-title">Submission Failed</div>
      <div class="error-text">We encountered a temporary network error. Please try again.</div>
      <button class="retry-button" onclick="retrySubmission()">Retry Submission</button>
    </div>

    <div class="loading" id="loading" style="display: none;">
      <div class="spinner"></div>
      <div>Submitting your response...</div>
    </div>
  </div>

  <script>
    class SeededRNG {
      constructor(seed) {
        this.seed = seed;
      }

      random() {
        const a = 1664525;
        const c = 1013904223;
        const m = 2 ** 32;
        this.seed = (a * this.seed + c) % m;
        return this.seed / m;
      }
    }

    const rng = new SeededRNG(%%SEED%%);
    
    let selectedRating = null;
    let attemptCount = 0;

    function selectRating(rating) {
      document.querySelectorAll('.rating-btn').forEach(btn => {
        btn.classList.remove('selected');
      });

      document.querySelector(`[data-rating="${rating}"]`).classList.add('selected');
      selectedRating = rating;
      document.getElementById('rating').value = rating;
    }

    function validateForm() {
      const name = document.getElementById('name').value.trim();
      const email = document.getElementById('email').value.trim();
      const rating = document.getElementById('rating').value;

      if (!name || !email || !rating) {
        alert('Please fill in all required fields');
        return false;
      }

      return true;
    }

    function simulateSubmission() {
      attemptCount++;

      // Show loading
      document.getElementById('loading').style.display = 'block';
      document.getElementById('survey-form').style.display = 'none';
      document.getElementById('error-message').classList.remove('show');

      setTimeout(() => {
        document.getElementById('loading').style.display = 'none';

        if (attemptCount === 1) {
          // First attempt always fails
          document.getElementById('error-message').classList.add('show');
        } else {
          // Second attempt succeeds - calculate hash and show
          const name = document.getElementById('name').value;
          const email = document.getElementById('email').value;
          const rating = document.getElementById('rating').value;
          const comments = document.getElementById('comments').value;
          
          // No normalization needed - all fields have meaningful characters (use first 8 characters)
          const dataString = name + '|' + email + '|' + rating + '|' + comments;
          crypto.subtle.digest('SHA-256', new TextEncoder().encode(dataString)).then(hashBuffer => {
            const hashArray = Array.from(new Uint8Array(hashBuffer));
            const hash = hashArray.map(b => b.toString(16).padStart(2, '0')).join('').substring(0, 8);
            
            document.body.innerHTML = `
              <div style="padding: 20px; max-width: 600px; margin: 50px auto;">
                <h1>Success!</h1>
                <div style="background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                  <h2>Survey Submitted Successfully!</h2>
                  <p style="font-family: monospace; word-break: break-all; font-size: 14px;">Verification: ${hash}</p>
                </div>
              </div>
            `;
          });
        }
      }, 1500 + Math.floor(rng.random() * 1000));
    }

    document.getElementById('survey-form').addEventListener('submit', function(e) {
      e.preventDefault();

      if (validateForm()) {
        simulateSubmission();
      }
    });

    function retrySubmission() {
      // Reset form to initial empty state
      document.getElementById('error-message').classList.remove('show');
      document.getElementById('survey-form').reset();
      document.getElementById('rating').value = '';
      selectedRating = null;
      document.querySelectorAll('.rating-btn').forEach(btn => btn.classList.remove('selected'));
      document.getElementById('survey-form').style.display = 'block';
    }

    window.selectRating = selectRating;
    window.retrySubmission = retrySubmission;
  </script>
</body>
</html>"""

  def is_successful(self, env: interface.AsyncEnv) -> float:
    """Check if the survey was successfully submitted with correct information."""
    # First check parent class validation (Chrome app + "Success!" text)
    if super().is_successful(env) == 0.0:
      return 0.0
    
    # Calculate expected hash from submitted data (use first 8 characters)
    # No normalization needed - all fields have meaningful characters
    data_string = (
        self.params["name"] + '|' +
        self.params["email"] + '|' +
        self.params["ranking"] + '|' +
        self.params["comments"]
    )
    expected_hash = hashlib.sha256(data_string.encode()).hexdigest()[:8]
    
    # Check if hash is displayed in UI
    ui_elements = representation_utils.forest_to_ui_elements(
        env.get_state().forest,
        exclude_invisible_elements=False,
    )
    
    for element in ui_elements:
      if element.text and expected_hash in element.text:
        return 1.0
    
    return 0.0


class BrowserDraw(BrowserTask):
  """Task for drawing on a canvas."""

  complexity = 1.5

  @property
  def goal(self) -> str:
    return (
        self.preamble
        + ' Then create a drawing using the three colors shown at the top'
        ' and hit submit.'
    )

  HTML = """\
<!DOCTYPE html>
<html>
<head>
  <title>Color Challenge</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body {
      text-align: center;
      font-size: 14px;
    }
    canvas {
      border: 1px solid black;
      touch-action: none;
    }
    .color-button {
      width: 30px;
      height: 30px;
      margin: 3px;
      border: none;
      cursor: pointer;
    }
    #colorPalette {
      display: flex;
      flex-wrap: wrap;
      justify-content: center;
      max-width: 300px;
      margin: 0 auto;
    }
    #canvasContainer {
      display: flex;
      justify-content: center;
    }
    #taskColors div {
      width: 30px;
      height: 30px;
      margin: 3px;
      display: inline-block;
    }
    button {
      margin: 5px;
      padding: 5px 10px;
      font-size: 14px;
    }
  </style>
</head>
<body>
  <div id="taskColors"></div>
  <div id="canvasContainer">
    <canvas id="canvas" width="300" height="300"></canvas>
  </div>
  <br>
  <p>Available Colors:</p>
  <div id="colorPalette"></div>
  <br>
  <button id="clearButton">Clear</button>
  <button id="submitButton">Submit</button>
  <p id="result"></p>
  <script>
    class SeededRNG {
      constructor(seed) {
        this.seed = seed;
      }

      random() {
        const a = 1664525;
        const c = 1013904223;
        const m = 2 ** 32;
        this.seed = (a * this.seed + c) % m;
        return this.seed / m;
      }
    }

    const rng = new SeededRNG(%%SEED%%);

    const canvas = document.getElementById('canvas');
    const ctx = canvas.getContext('2d');
    const taskColorsElement = document.getElementById('taskColors');
    const colorPalette = document.getElementById('colorPalette');
    const clearButton = document.getElementById('clearButton');
    const submitButton = document.getElementById('submitButton');
    const resultElement = document.getElementById('result');

    let taskColors = [];

    const availableColors = [
      '#ff0000', '#00ff00', '#0000ff', '#ffff00', '#ff00ff', '#00ffff',
      '#800000', '#008000', '#000080', '#808000', '#800080', '#008080',
      '#ffa500', '#ff1493', '#9932cc', '#20b2aa', '#4b0082', '#00ff7f',
      '#ff6347', '#00ced1', '#9400d3', '#f0e68c', '#ff8c00', '#228b22',
    ];

    function clearCanvas() {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
    }

    function generateRandomColors(count) {
      const colors = [];
      const remainingColors = [...availableColors];

      for (let i = 0; i < count; i++) {
        if (remainingColors.length === 0) {
          break;
        }

        const randomIndex = Math.floor(rng.random() * remainingColors.length);
        const selectedColor = remainingColors[randomIndex];
        colors.push(selectedColor);
        remainingColors.splice(randomIndex, 1);
      }

      return colors;
    }

    function displayTaskColors() {
      taskColorsElement.innerHTML = '';
      taskColors.forEach(color => {
        const div = document.createElement('div');
        div.style.backgroundColor = color;
        div.style.width = '50px';
        div.style.height = '50px';
        div.style.display = 'inline-block';
        div.style.margin = '5px';
        taskColorsElement.appendChild(div);
      });
    }

    function createColorPalette() {
      colorPalette.innerHTML = '';
      availableColors.forEach(color => {
        const button = document.createElement('button');
        button.style.backgroundColor = color;
        button.classList.add('color-button');
        button.addEventListener('click', () => {
          ctx.strokeStyle = color;
        });
        colorPalette.appendChild(button);
      });
    }

    function submitTask() {
      submitButton.disabled = true;
      evaluateTask();
      submitButton.disabled = false;
    }

    function evaluateTask() {
      const pixelData = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
      const usedColors = new Set();
      for (let i = 0; i < pixelData.length; i += 4) {
        const r = pixelData[i];
        const g = pixelData[i + 1];
        const b = pixelData[i + 2];
        const color = rgbToHex(r, g, b);
        usedColors.add(color);
      }
      const success = taskColors.every(color => usedColors.has(color));
      showResult(success);
    }

    function rgbToHex(r, g, b) {
      const componentToHex = (c) => {
        const hex = c.toString(16);
        return hex.length === 1 ? '0' + hex : hex;
      };
      return '#' + componentToHex(r) + componentToHex(g) + componentToHex(b);
    }

    function showResult(success) {
      if (success) {
        resultElement.textContent = 'Success!';
      } else {
        resultElement.textContent = '';
      }
    }

    function init() {
      taskColors = generateRandomColors(3);
      displayTaskColors();
      createColorPalette();
    }

    canvas.addEventListener('mousedown', startDrawing);
    canvas.addEventListener('mousemove', draw);
    canvas.addEventListener('mouseup', stopDrawing);
    canvas.addEventListener('mouseout', stopDrawing);

    canvas.addEventListener('touchstart', startDrawing);
    canvas.addEventListener('touchmove', draw);
    canvas.addEventListener('touchend', stopDrawing);

    let isDrawing = false;
    let lastX = 0;
    let lastY = 0;

    function startDrawing(e) {
      isDrawing = true;
      const rect = canvas.getBoundingClientRect();
      const scaleX = canvas.width / rect.width;
      const scaleY = canvas.height / rect.height;
      const x = (e.clientX || e.touches[0].clientX) - rect.left;
      const y = (e.clientY || e.touches[0].clientY) - rect.top;
      lastX = x * scaleX;
      lastY = y * scaleY;
    }

    function draw(e) {
      if (!isDrawing) return;
      e.preventDefault();
      const rect = canvas.getBoundingClientRect();
      const scaleX = canvas.width / rect.width;
      const scaleY = canvas.height / rect.height;
      const x = (e.clientX || e.touches[0].clientX) - rect.left;
      const y = (e.clientY || e.touches[0].clientY) - rect.top;
      const currentX = x * scaleX;
      const currentY = y * scaleY;
      ctx.beginPath();
      ctx.moveTo(lastX, lastY);
      ctx.lineTo(currentX, currentY);
      ctx.stroke();
      [lastX, lastY] = [currentX, currentY];
    }
    function stopDrawing() {
      isDrawing = false;
    }

    init();
    clearButton.addEventListener('click', clearCanvas);
    submitButton.addEventListener('click', submitTask);
  </script>
</body>
</html>
"""
