---
dataset_info:
  num_examples: 39
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

**39 before/after pairs** of DNA nanostructure design operations.

Each example contains:
- `before_image`: Screenshot before the operation
- `after_image`: Screenshot after the operation
- `instruction`: Natural language description of what to do
- `operation`: Method name that was called
- `category`: High-level operation category

## Categories

- **crossover_move**: 15 examples
- **crossover_add**: 11 examples
- **insertion**: 5 examples
- **strand_break**: 4 examples
- **strand_resize**: 4 examples
