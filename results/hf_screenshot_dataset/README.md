---
dataset_info:
  num_examples: 33
  features:
    - name: before_image
      dtype: image
    - name: after_image
      dtype: image
    - name: instruction
      dtype: string
    - name: operation
      dtype: string
    - name: category
      dtype: string
task_categories:
  - image-to-image
  - visual-question-answering
---

# cadnano Screenshot Training Dataset

**33 before/after pairs** of DNA nanostructure design operations.

Each example contains:
- `before_image`: Screenshot before the operation
- `after_image`: Screenshot after the operation
- `instruction`: Natural language description of what to do
- `operation`: Method name that was called
- `category`: High-level operation category

## Categories

- **crossover_move**: 14 examples
- **crossover_add**: 9 examples
- **insertion**: 4 examples
- **strand_break**: 3 examples
- **strand_resize**: 3 examples
