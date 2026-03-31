// Minimal DOM mock for testing
global.document = {
  createElement: (tag) => {
    const element = {
      tag,
      attributes: {},
      children: [],
      style: {},
      classList: {
        add: function(className) {
          this._classes = this._classes || [];
          if (!this._classes.includes(className)) {
            this._classes.push(className);
          }
        },
        remove: function(className) {
          this._classes = this._classes || [];
          this._classes = this._classes.filter(c => c !== className);
        },
        contains: function(className) {
          this._classes = this._classes || [];
          return this._classes.includes(className);
        },
        _classes: []
      },
      id: '',
      _textContent: '',
      _innerHTML: '',
      get textContent() {
        return this._textContent;
      },
      set textContent(value) {
        this._textContent = value;
        // Update innerHTML to show the content
        this._innerHTML = this._textContent;
      },
      get innerHTML() {
        if (this.children.length > 0) {
          // Build HTML representation from children
          return this.children.map(child => {
            if (child.tag === 'pre') {
              return `<pre>${child._textContent}</pre>`;
            }
            return '';
          }).join('');
        }
        return this._innerHTML;
      },
      set innerHTML(value) {
        this._innerHTML = value;
        this.children = [];
      },
      appendChild: function(child) {
        this.children.push(child);
      },
      querySelector: function(selector) {
        if (selector === 'pre') {
          return this.children.find(c => c.tag === 'pre');
        }
        return null;
      },
      setAttribute: function(name, value) {
        this.attributes[name] = value;
      },
      getAttribute: function(name) {
        return this.attributes[name];
      },
      addEventListener: function() {},
      removeEventListener: function() {}
    };
    return element;
  },
  body: {
    appendChild: function(element) {
      this._children = this._children || [];
      this._children.push(element);
    },
    innerHTML: '',
    querySelectorAll: function() {
      return [];
    }
  }
};

global.window = {
  document: global.document,
  setTimeout: setTimeout,
  clearTimeout: clearTimeout
};
